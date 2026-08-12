import logging
import warnings
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from extractor.extractor import EpubExtractor
from extractor.image import extract_images
from extractor.json import write_json
from extractor.pipeline import Pipeline, TextClassifier, TitleBasedTypeInference

logger = logging.getLogger(__name__)


def to_ordered_dict(data: Any) -> Any:
    """Recursively converts dictionaries to OrderedDict."""
    if isinstance(data, dict):
        return OrderedDict((k, to_ordered_dict(v)) for k, v in data.items())
    if isinstance(data, list):
        return [to_ordered_dict(v) for v in data]
    return data


class BulkProcessor:
    def __init__(
        self,
        output_dir: Path,
        model_path: Path,
        strict: bool = False,
        include_images: bool = True,
        skip_existing: bool = False,
    ):
        self.output_dir = Path(output_dir)
        # If the output_dir is already named 'json_final', use it directly.
        # Otherwise, create a 'json_final' subdirectory.
        if self.output_dir.name == "json_final":
            self.json_final_dir = self.output_dir
        else:
            self.json_final_dir = self.output_dir / "json_final"
        
        self.json_final_dir.mkdir(exist_ok=True, parents=True)

        self.extractor = EpubExtractor(
            merciful=not strict, include_images=include_images
        )
        self.include_images = include_images
        self.model_path = model_path
        self.skip_existing = skip_existing

        # Initialize components individually for granular reporting
        self.type_inference = TitleBasedTypeInference()
        self.classifier = TextClassifier(model_path=model_path)

    def process_book(self, epub_path: Path) -> Dict:
        """Processes a single book through the entire pipeline."""
        status = {
            "path": str(epub_path.absolute()),
            "steps": {
                "extraction": "pending",
                "type_inference": "pending",
                "classification": "pending",
                "serialization": "pending",
            },
            "error": None,
            "skipped": False,
        }

        try:
            # Setup specific folder for this book.
            # Use parent directory name (DNB ID) as the folder name.
            book_output_dir = self.json_final_dir / epub_path.parent.name
            final_json_path = book_output_dir / f"{epub_path.stem}.json"

            if self.skip_existing and final_json_path.exists():
                logger.info(f"Skipping {epub_path} as output already exists.")
                status["skipped"] = True
                for step in status["steps"]:
                    status["steps"][step] = "skipped"
                return status

            # 1. Extraction
            logger.info(f"Extracting {epub_path}")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                extracted = self.extractor(epub_path)
            
            # Ensure we are working with OrderedDict for pipeline compatibility
            extracted = to_ordered_dict(extracted)
            status["steps"]["extraction"] = "success"

            # 2. Image Handling (if applicable)
            # Setup specific folder for this book
            book_output_dir.mkdir(exist_ok=True, parents=True)
            if self.include_images:
                logger.info(f"Extracting images for {epub_path}")
                extract_images(extracted, book_output_dir / "imgs")

            # 3. Type Inference
            logger.info(f"Running type inference for {epub_path}")
            extracted = self.type_inference(extracted, epub_path)
            status["steps"]["type_inference"] = "success"

            # 4. Classification
            logger.info(f"Running classification for {epub_path}")
            extracted = self.classifier(extracted, epub_path)
            status["steps"]["classification"] = "success"
            
            # 5. Final Serialization
            write_json(extracted, final_json_path)
            status["steps"]["serialization"] = "success"

        except Exception as e:
            logger.exception(f"Error processing {epub_path}")
            status["error"] = str(e)
            # Find the first pending step and mark it as failed
            for step, state in status["steps"].items():
                if state == "pending":
                    status["steps"][step] = "failed"
                    break

        return status

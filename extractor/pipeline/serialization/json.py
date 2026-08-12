import logging
import shutil
from pathlib import Path
from typing import Dict, Optional, Union

from extractor.json import write_json

from ..base import BasePipelineComponent
from ..type_inference import is_collection

logger = logging.getLogger(__name__)


class JSONSerializer(BasePipelineComponent):
    CUSTOM_DESCRIPTION = {"description": "Write out JSON files. "}

    def __init__(
        self, output_dir: Optional[Union[str, Path]] = None, copy_images: bool = False
    ):
        """
        Identify transform pipeline component that writes out the JSON data to a file.
        """
        # TODO find elegant way to handle none default values in CLI arg parsing
        if isinstance(output_dir, str):
            output_dir = None if output_dir.lower() == "none" else output_dir
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = None
        self.copy_images = copy_images
        if copy_images and output_dir is None:
            logger.warning(
                "Copy images won't have any effect since no new output_dir is"
                " specified."
            )

    def process(self, extracted: Dict, file_path: Path) -> Dict:
        if self.output_dir is not None:
            # Setup new dir
            new_output_dir = self.output_dir / file_path.parent.name
            new_output_dir.mkdir(exist_ok=True, parents=True)
            # If desired copy images
            if self.copy_images:
                orig_img_dir = file_path.parent / "imgs"
                assert (
                    orig_img_dir.is_dir() and orig_img_dir.exists()
                ), f"{orig_img_dir} does not exist"
                new_img_dir = new_output_dir / "imgs"
                shutil.copytree(str(orig_img_dir), str(new_img_dir), dirs_exist_ok=True)
            # Overwrite file_path
            file_path = new_output_dir / file_path.name

        write_json(extracted, file_path)
        return extracted

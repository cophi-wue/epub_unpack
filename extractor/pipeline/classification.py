import logging
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Optional, Union

import joblib

from .base import BaseContentPipelineComponent

logger = logging.getLogger(__name__)


class TextClassifier(BaseContentPipelineComponent):
    """
    Pipeline component that uses a trained classifier to label text segments as narrative or non-narrative.
    """

    ADDED_FIELDS = ["is_narrative"]
    CUSTOM_DESCRIPTION = {
        "description": "Classify text segments into narrative/non-narrative using a trained model."
    }

    def __init__(self, model_path: Union[str, Path]) -> None:
        super().__init__()
        self.model_path = Path(model_path)
        self._model = None

    @property
    def model(self):
        if self._model is None:
            if not self.model_path.exists():
                raise FileNotFoundError(f"Classifier model not found at {self.model_path}")
            logger.info(f"Loading classifier model from {self.model_path}")
            self._model = joblib.load(self.model_path)
        return self._model

    def remove_xml_tags(self, text: str) -> str:
        """Removes XML/HTML tags from text."""
        return re.sub(r"<.*?>", "", text)

    def process_html(self, html_elem: OrderedDict, file_path: Path) -> None:
        text = html_elem.get("text", "")
        if text:
            clean_text = self.remove_xml_tags(str(text))
            # Use the model to predict
            # Note: predict expects a list of samples
            prediction = self.model.predict([clean_text])[0]
            html_elem["is_narrative"] = bool(prediction)
        else:
            html_elem["is_narrative"] = False

    def process_section(self, section: OrderedDict, file_path: Path) -> None:
        # Sections themselves don't have 'text' in this schema,
        # but their children (EpubHtml) do.
        pass

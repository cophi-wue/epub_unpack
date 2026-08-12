from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

from tqdm.auto import tqdm

from extractor.utils import get_timestamp


class Pipeline:
    def __init__(
        self, components: Sequence[BasePipelineComponent], pbar: bool = False
    ) -> None:
        self.components = components
        self.pbar = pbar

    def __call__(self, extracted: OrderedDict, file_path: Path) -> OrderedDict:
        if self.pbar:
            component_iterator = tqdm(self.components)
        else:
            component_iterator = iter(self.components)
        # Set up entry in processing log
        if "component_log" not in extracted["processing_log"]:
            extracted["processing_log"]["component_log"] = []

        for component in component_iterator:
            if self.pbar:
                component_iterator.set_description(
                    f"Applying {component.__class__.__name__}"
                )
                component_iterator.refresh()
            extracted = component(extracted, file_path)
            extracted["processing_log"]["component_log"].append(component.log_entry)

        return extracted


class BasePipelineComponent:
    COPY = False

    ADDED_FIELDS: Optional[List[str]] = None
    ALTERED_FIELDS: Optional[List[str]] = None
    CUSTOM_DESCRIPTION: Optional[Dict] = None

    def __call__(self, extracted: OrderedDict, file_path: Path) -> OrderedDict:
        if self.COPY:
            extracted = deepcopy(extracted)
        return self.process(extracted, file_path)

    def process(self, extracted: OrderedDict, file_path: Path) -> OrderedDict:
        raise NotImplementedError

    @property
    def log_entry(self):
        log_entry = {"name": self.__class__.__name__, "timestamp": get_timestamp()}
        if self.ADDED_FIELDS is not None:
            log_entry["added_fields"] = self.ADDED_FIELDS
        if self.ALTERED_FIELDS is not None:
            log_entry["altered_fields"] = self.ALTERED_FIELDS
        if self.CUSTOM_DESCRIPTION is not None:
            log_entry |= self.CUSTOM_DESCRIPTION
        return log_entry


class BaseContentPipelineComponent(BasePipelineComponent):
    """
    A pipeline component to process the contents of an extracted EPUB.
    Iterates over all elements in the content in textual order.
    Allows dedicated handling of Section and EpubHTML parts
    """

    def process(self, extracted: OrderedDict, file_path: Path) -> OrderedDict:
        def _recurse(elem: Union[OrderedDict, List]):
            if elem["type"] == "EpubHtml":
                self.process_html(elem, file_path=file_path)
            elif elem["type"] == "Section":
                self.process_section(elem, file_path=file_path)
                for elem in elem["content"]:
                    _recurse(elem)

        for elem in extracted["content"]:
            _recurse(elem)

        return extracted

    def process_html(self, html_elem: OrderedDict, file_path: Path) -> None:
        """
        Define inplace operations on any html_element.
        """
        raise NotImplementedError

    def process_section(self, section: OrderedDict, file_path: Path) -> None:
        """
        Define inplace operations on any section.
        Changes are applied BEFORE the section content is traversed!
        """
        raise NotImplementedError


class PrintComponent(BaseContentPipelineComponent):
    CUSTOM_DESCRIPTION = {
        "description": (
            "Does nothing, and just prints out texts while processing. For debugging/"
            " testing."
        )
    }

    def __init__(self, shout: bool = False) -> None:
        """Print out the content to stdout

        Args:
            shout (bool, optional): Convert everything to UPPER-CASE. Defaults to False.
        """
        self.shout = shout

    def process_html(self, html_elem: OrderedDict, file_path: Path) -> None:
        if not self.shout:
            print(html_elem["text"])
        else:
            print(html_elem["text"].upper())

    def process_section(self, section: OrderedDict, file_path: Path) -> None:
        ...

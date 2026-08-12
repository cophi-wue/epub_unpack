import re
from pathlib import Path

import lxml.etree as et

from .utils import (
    lxml_parse_xml_from_string,
    lxml_parse_xslt_from_string,
    time_call,
    xsltproc_transformation,
)


class TEITextPostProcessor:
    """
    Applies some post-processing steps to the converted TEI content.
    """

    POST_PROCESS_STYLESHEET_PATH = "xslt/htmltotei_postprocess.xslt"

    def __init__(self) -> None:
        self.stylesheet: str = (
            Path(__file__).parent / self.POST_PROCESS_STYLESHEET_PATH
        ).read_text()
        self.xslt_processor = lxml_parse_xslt_from_string(self.stylesheet)
        self.body_regex = re.compile(r"<body>(.*)<\/body>", re.DOTALL)

    def __call__(self, tei_xml: str) -> str:
        tei_xml = self._apply_transformations(tei_xml=tei_xml)
        tei_xml = self._get_body(tei_xml=tei_xml)
        return tei_xml

    def _apply_transformations(self, tei_xml: str) -> str:
        doc = lxml_parse_xml_from_string(tei_xml)
        transformed_doc = self.xslt_processor(doc)
        return et.tostring(transformed_doc, method="xml").decode("utf-8")
        # return xsltproc_transformation(self.stylesheet, tei_xml)

    def _get_body(self, tei_xml: str) -> str:
        match = self.body_regex.search(tei_xml)
        if match is None and "<body/>" in tei_xml:
            return ""
        return match.group(1)

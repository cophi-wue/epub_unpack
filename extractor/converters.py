"""
NOTE: The content of this file is currently deprecated, and just kept for legacy reasons.
"""

import logging
import re
import subprocess
import tempfile
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Optional, Union

import css_inline
from bs4 import BeautifulSoup
from ebooklib import epub
from lxml import etree as et
from saxonche import PySaxonProcessor

from .exceptions import SaxonException
from .namespaces import XML_NAMESPACES
from .utils import (
    change_cwd,
    get_location,
    html2xml,
    lxml_parse_xml_from_string,
    lxml_parse_xslt_from_string,
    time_call,
)

logger = logging.getLogger(__name__)


class Body2TEIConverter:
    """
    New experimental module to extract text from a HTML-document's body,
    and convert into a TEI format.
    """

    def __init__(
        self,
        xslt_stylesheet_path: Optional[Union[str, Path]] = None,
        mode: Optional[str] = None,
    ) -> None:
        self.inline_converter = css2inline

        if xslt_stylesheet_path is None:
            xslt_stylesheet_path = Path(__file__).parent / "xslt/html2tei.xslt"

        if isinstance(xslt_stylesheet_path, str):
            xslt_stylesheet_path = Path(xslt_stylesheet_path)

        self.mode = mode.lower() if mode is not None else "lxml"
        if self.mode == "lxml":
            self.xslt_processor = et.XSLT(et.XML(xslt_stylesheet_path.read_text()))
        elif self.mode == "saxon":
            self.xslt_processor = self.make_saxon_xslt_processor(xslt_stylesheet_path)
        else:
            raise ValueError(
                f"Invalid value '{mode}' for param mode. Can either be 'lxml' or"
                " 'saxon'"
            )

    def make_saxon_xslt_processor(self, xslt_stylesheet_path: Path):
        xml_processor = PySaxonProcessor(license=False)
        xslt_processor = xml_processor.new_xslt30_processor()

        def processor(content: str) -> str:
            xml_content = html2xml(content)
            document = xml_processor.parse_xml(xml_text=xml_content)
            xml_processor
            stylesheet = xslt_processor.compile_stylesheet(
                stylesheet_file=str(xslt_stylesheet_path.absolute())
            )
            output = stylesheet.transform_to_string(xdm_node=document)

            if stylesheet.exception_occurred:
                raise SaxonException("Check stdout for more information.")

            return output

        return processor

    def __call__(self, html: epub.EpubHtml, unzipped_dir: Path) -> Union[str, None]:
        inline_html = self.inline_converter(html=html, unzipped_dir=unzipped_dir)
        soup = BeautifulSoup(inline_html)
        body = soup.find("body")
        content = body.decode_contents()

        if self.mode == "lxml":
            content = self.html2tei_lxml(content)
        elif self.mode == "saxon":
            content = self.html2tei_saxon(content)

        return content

    def style2inline(self, html: epub.EpubHtml, unzipped_dir: Path) -> str:
        html_parent = get_location(html.file_name, unzipped_dir).parent
        with change_cwd(html_parent):
            content = html.content.decode("utf-8")
            # content = unicodedata.normalize("NFD", content)
            inline_content = css_inline.inline(content)
        return inline_content

    def html2tei_saxon(self, content: str):
        if not content.strip():
            return None
        tei_string = (
            self.xslt_processor(content)
            .replace("<p>\n</p>", "\n")
            .removeprefix("<html><body>")
            .removesuffix("</body></html>")
            # TODO This needs a more serious fix!
            .replace('xmlns=""', "")
            .strip()
        )
        return tei_string

    def html2tei_lxml(self, content: str):
        if not content.strip():
            return None
        lxml_html = et.parse(
            StringIO(content), et.HTMLParser(recover=True, no_network=True)
        )
        # Apply XSLT-transformation, and do some manual cleaning of the transformed output
        try:
            transformed = self.xslt_processor(lxml_html)
        except Exception as e:
            logger.critical(repr(content))
            raise e
        tei_string = (
            et.tostring(transformed, pretty_print=True, method="xml")
            .decode("utf-8")
            .replace("<p>\n</p>", "\n")
            .removeprefix("<html><body>")
            .removesuffix("</body></html>")
            # TODO This needs a more serious fix!
            .replace('xmlns=""', "")
            .strip()
        )
        return tei_string

    def apply_lxml_transformations(content: str):
        doc = et.parse(StringIO(content), et.XMLParser(recover=True))

        # Wrap stars scenes in div
        def wrap_star_scenes(doc):
            temp_root = et.Element("temp_root")

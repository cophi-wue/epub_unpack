import datetime
import json
import os
import subprocess
import tempfile
from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from timeit import default_timer
from typing import Any, Callable, Generator, Iterable, List, Optional, Type, Union

import css_inline
import lxml.etree as et
from bs4 import BeautifulSoup
from ebooklib import epub
from lxml import etree as et
from lxml import html

from .exceptions import CalibreConversionError, XSLTProcException

REMOVE_STYLE_XSLT = """
<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:tei="http://www.tei-c.org/ns/1.0">
    <xsl:template match="@*|node()">
        <xsl:copy>
            <xsl:apply-templates select="@*|node()"/>
        </xsl:copy>
    </xsl:template>
    <xsl:template match="tei:{target_elem}/@style"></xsl:template>  
</xsl:stylesheet>
""".strip()


def remove_style_attributes(tei: str, target_elem: Optional[str] = None) -> str:
    """Removes style attributes from the selected attributes (default <p>) in a TEI document.

    Args:
        tei (str): TEI document as string
        target_elem (Optional[str], optional): Element to remove style attributes from. Defaults to <p>.

    Returns:
        str: TEI document with styles removed
    """

    if target_elem is None:
        target_elem = "p"

    doc = lxml_parse_xml_from_string(tei)
    xslt_processor = et.XSLT(
        et.parse(
            BytesIO(REMOVE_STYLE_XSLT.format(target_elem=target_elem).encode("utf-8"))
        )
    )
    transformed_doc = xslt_processor(doc)
    tei_transformed = et.tostring(
        transformed_doc, pretty_print=True, method="xml"
    ).decode("utf-8")

    return tei_transformed


def css2inline(
    html: epub.EpubHtml, unzipped_dir: Path, ignore_errors: bool = True
) -> str:
    html_parent = get_location(html.file_name, unzipped_dir).parent
    with change_cwd(html_parent):
        content = html.content.decode("utf-8")
        try:
            inline_content = css_inline.inline(content)
        except css_inline.InlineError as e:
            if ignore_errors:
                inline_content = html.content.decode("utf-8")
            else:
                raise e
    return inline_content


def prevent_overwrite(path: Path) -> Path:
    if not path.exists():
        return path
    i = 1
    while True:
        new_path = path.parent / (path.stem + f"_{i}" + path.suffix)
        if not new_path.exists():
            return new_path
        i += 1


def html2xml(content: str, mode="lxml") -> str:
    """Converts HTML into well-formed xml

    Args:
        content (str): HTML-document
        mode (str): Whether to use BeautifulSoup's prettify function or lxml to convert HTML to XML. Defaults to 'lxml'

    Returns:
        str: well-formed XML document
    """
    mode = mode.lower()
    content_n_newlines = content.count("\n")
    if mode == "soup":
        soup = BeautifulSoup(content, "lxml")
        xml = soup.prettify()
    elif mode == "lxml":
        doc = html.fromstring(content)
        xml = et.tostring(doc, encoding="unicode", pretty_print=False)
    xml_n_newlines = content.count("\n")
    assert content_n_newlines == xml_n_newlines
    return xml


def remove_duplicates(l: List[Any]) -> List[Any]:
    """Removes duplicates from a list

    Args:
        l (List[Any]):

    Returns:
        List[Any]: List with filtered contents.
    """
    return list(dict.fromkeys(l))


def consume_generator(func: Callable[[Any], Generator]) -> List[Any]:
    """Wraps a function returning a generator and making it return a list of results instead of the generator.

    Args:
        func (Callable[[Any], Generator]): Any function that returns a generator.

    Returns:
        List[Any]: List of results.
    """

    def wrapper(*args, **kwargs):
        return list(func(*args, **kwargs))

    return wrapper


def any_is_type(collection: Iterable[Any], type: Type) -> bool:
    """TODO: docs

    Args:
        collection (Iterable[Any]): _description_
        type (Type): _description_

    Returns:
        bool: _description_
    """
    for entry in collection:
        if isinstance(entry, type):
            return True
    return False


@contextmanager
def change_cwd(cwd: Union[str, Path]):
    origin = os.getcwd()
    try:
        os.chdir(cwd)
        yield
    finally:
        os.chdir(origin)


def get_location(file: Union[str, Path], directory: Union[str, Path]) -> Path:
    if isinstance(file, str):
        file = Path(file)
    if isinstance(directory, str):
        directory = Path(directory)
    try:
        return next(directory.glob(f"**/{file}"))
    except StopIteration:
        return None


def lxml_parse_xml_from_string(string: str) -> et.ElementTree:
    doc = et.parse(
        BytesIO(string.encode("utf-8")),
        parser=et.XMLParser(ns_clean=True, recover=True, encoding="utf-8"),
    )
    return doc


def lxml_parse_xslt_from_string(string: str) -> et.XSLT:
    xslt_processor = et.XSLT(et.parse(BytesIO(string.encode("utf-8"))))
    return xslt_processor


def time_call(func):
    def wrapper(*args, **kwargs):
        start = default_timer()
        result = func(*args, **kwargs)
        end = default_timer()
        elapsed = end - start
        print(f"Time elapsed during executing function {func.__name__}: {elapsed:.4f}")
        return result

    return wrapper


def string2clipboard(string: str) -> None:
    import pandas as pd

    df = pd.DataFrame([string])
    df.to_clipboard(excel=False, index=False, header=False)


def xsltproc_transformation(xslt_stylesheet: str, xml: str):
    def apply_transformation(xslt_file: Path, xml_file: Path) -> str:
        try:
            output = subprocess.run(
                ["xsltproc", xslt_file.absolute(), xml_file.absolute()],
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise XSLTProcException(e.stderr)
        return output.stdout.decode("utf-8")

    with tempfile.NamedTemporaryFile(
        mode="w", prefix="stylesheet_", suffix=".xslt"
    ) as xslt_file:
        with tempfile.NamedTemporaryFile(
            mode="w", prefix="document_", suffix=".xml"
        ) as xml_file:
            xslt_file.write(xslt_stylesheet)
            xslt_file.seek(0)
            xml_file.write(xml)
            xml_file.seek(0)
            transformed_xml = apply_transformation(
                xslt_file=Path(xslt_file.name), xml_file=Path(xml_file.name)
            )
    return transformed_xml


def get_timestamp():
    now = datetime.datetime.now()
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%S") + "-%02d" % (now.microsecond / 10000)
    return timestamp


def calibre_convert(
    input_file: Union[Path, str], output_file: Union[Path, str]
) -> None:
    input_file, output_file = map(Path, (input_file, output_file))
    try:
        args = [
            "ebook-convert",
            str(input_file.absolute()),
            str(output_file.absolute()),
        ]
        _ = subprocess.run(args=args, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise CalibreConversionError(e.stderr.decode("utf-8"))

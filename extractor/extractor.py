import html
import logging
import os
import re
import subprocess
import tempfile
import time
import warnings
import zipfile
from collections import UserList, namedtuple
from pathlib import Path
from sys import maxsize as MAX_INT
from typing import Dict, Generator, List, Optional, Tuple, Union
from urllib import parse

import ebooklib
import lxml.etree as et
from bs4 import BeautifulSoup
from ebooklib import epub
from tqdm.auto import tqdm

from .exceptions import LinkResolveException, SanityCheckException, SaxonException
from .image import Image
from .namespaces import XML_NAMESPACES
from .post_processors import TEITextPostProcessor
from .sanity_checks import chapters_are_consecutive, contains_duplicate_texts
from .temporary_file_strings import TemporaryFileString, TemporaryFileStringDir
from .utils import (
    any_is_type,
    calibre_convert,
    consume_generator,
    css2inline,
    get_location,
    html2xml,
)

logger = logging.getLogger(__name__)


if (env_saxon_path := os.environ.get("SAXON_PATH", None)) is None:
    SAXON_PATH = Path(__file__).parent / "xslt/Stylesheets/lib/saxon10he.jar"
else:
    SAXON_PATH = Path(env_saxon_path)


TableOfContents = List[Union[epub.Link, Tuple[epub.Section, Tuple[epub.Link]]]]


class MultiLevelList(UserList):
    """
    Custom list-like datatype that supports indexing and inserting into nested entries using a list of indices.
    """

    def __getitem__(self, query):
        if isinstance(query, int):
            return self.data[query]
        elif isinstance(query, list):
            elem = self.data[query[0]]
            for idx in query[1:]:
                elem = elem[idx]
            return elem
        else:
            raise IndexError(f"Type {type(query)} is not supported")

    def insert(self, index, data):
        if isinstance(index, int):
            self.data.insert(index, data)
        elif isinstance(index, list):
            addr, pointer = index[:-1], index[-1]
            if addr:
                elem = self.data[addr[0]]
                for idx in addr[1:]:
                    elem = elem[idx]
            else:
                elem = self.data
            elem.insert(pointer, data)
        else:
            raise IndexError(f"Type {type(index)} is not supported")


def get_href_index(
    toc: TableOfContents,
    href: str,
    multiple_matches: bool = False,
) -> Union[str, None, List[int]]:
    """Recurses the passed `.toc` attribute of an epub.EpubBook object
    and returns the (potentially nested) index of the content referenced with href.

    If `multiple_matches` is True a (potentially empty) List of match(es) is returned.
    Otherwise the index of the first match (or None) is returned.


    Args:
        toc (List[Union[epub.Link, Tuple[epub.Section, Tuple[epub.Link]]]]): _description_
        href (str): _description_
        multiple_matches (bool, optional): _description_. Defaults to False.

    Returns:
        Union[str, None, List[int]]: None, one or multiple matches.
    """

    def _recurse(toc, index=None):
        if index is None:
            index = []
        for idx, elem in enumerate(toc):
            if isinstance(elem, tuple):
                section, content = elem
                if section.href == href or sanitize_href(section.href) == href:
                    index.extend([idx, 0])
                    yield index
                else:
                    yield from _recurse(content, index=index + [idx, 1])
            else:
                if elem.href == href or sanitize_href(elem.href) == href:
                    index.append(idx)
                    yield index

    if multiple_matches:
        result = list(_recurse(toc))
    else:
        try:
            result = next(_recurse(toc))
        except StopIteration:
            result = None
    return result


def sanitize_href(href: str) -> str:
    """TODO: docs

    Args:
        href (str): _description_

    Returns:
        str: _description_
    """
    if "#" in href:
        href = href.split("#")[0]
    return href


def flatten_toc(toc: TableOfContents) -> List[Union[epub.Link, epub.Section]]:
    """TODO: docs

    Args:
        toc (List[Union[epub.Link, Tuple[epub.Section, Tuple[epub.Link]]]]): _description_

    Returns:
        List[Union[epub.Link, epub.Section]]: _description_
    """
    flattened_toc = []
    for entry in toc:
        if not isinstance(entry, tuple):
            flattened_toc.append(entry)
        else:
            flattened_toc.append(entry[0])
            flattened_toc.extend(entry[1])
    return flattened_toc


@consume_generator
def unravel_toc(toc: TableOfContents, level: int = 0, counter: int = 0) -> Generator:
    for elem in toc:
        if isinstance(elem, tuple):
            counter = 0
            yield [level + 1, counter, elem[0]]
            yield from unravel_toc(elem[1], level + 1, counter + 1)
        else:
            yield [level, counter, elem]
            counter += 1


class EpubExtractor:
    HTML2TEI_XSLT_STYLESHEET_PATH = (
        Path(__file__).parent / "xslt/Stylesheets/html/html2tei.xsl"
    )

    def __init__(
        self,
        merciful: bool = True,
        verbose: bool = False,
        include_images: bool = True,
        do_sanity_check: bool = False,
        debug: bool = False,
    ):
        self.merciful = merciful
        self.verbose = verbose
        self.tei_postprocessor = TEITextPostProcessor()
        self.include_images = include_images
        self.do_sanity_check = do_sanity_check
        self.debug = debug

    @staticmethod
    def contains_subsections(ebook: epub.EpubBook) -> bool:
        """Checks if the ebook's TOC contains sections.
        TODO: Name might be mispleading, rename it.

        Args:
            ebook (epub.EpubBook): Ebook to check

        Returns:
            bool: `True` if TOC contains one or more sections, else `False`
        """

        return any_is_type(flatten_toc(ebook.toc), epub.Section)

    def __call__(
        self, ebook_path: Union[str, Path]
    ) -> Dict[str, Union[str, List, Dict]]:
        """Loads an ebook from disk and converts its content into a json-serializable dictionary.

        Args:
            ebook_path (Union[str, Path]): Path to the *.epub-file

        Returns:
            Dict[str, Union[str, List, Dict]]: Content of the ebook.
        """
        self.book_log_ = {}

        ebook_path = Path(ebook_path)

        try:
            ebook = epub.read_epub(
                ebook_path, options={"ignore_ncx": True, "merciful": self.merciful}
            )
        except Exception as e:
            logger.warning(
                f"Loading {ebook_path} without ignoring failed, due to exception below."
                " Trying with ignoring."
            )
            logger.exception(e)

            ebook = epub.read_epub(
                ebook_path, options={"ignore_ncx": True, "merciful": self.merciful}
            )

        # Turns out we need access to the ebook object and the unzipped ebook more than once.
        # So the ebook is also unzipped here and a reference its temporary location is passed to the functions
        with tempfile.TemporaryDirectory() as unzipped_dir:
            unzipped_dir = Path(unzipped_dir)
            with zipfile.ZipFile(ebook_path) as zip_file:
                zip_file.extractall(unzipped_dir)

            ebook = self._sanitize_toc(ebook, unzipped_dir)
            self.book_log_["contain_subsections"] = self.contains_subsections(ebook)

            # Create temporary dir to write contents to
            temporary_content_dir = TemporaryFileStringDir()

            # Extract HTML content
            extracted = self._extract(
                ebook, ebook_path, unzipped_dir, temporary_content_dir
            )

            # Convert HTML to TEI
            self._html2tei(temporary_content_dir)
            temporary_content_dir.delete()

        # Add processing log to extracted content and perform sanity check.
        extracted["processing_log"] = self.book_log_
        if self.do_sanity_check:
            sanity_check_passed, len_extracted, len_calibre = self._sanity_check(
                extracted, ebook_path
            )
            if not sanity_check_passed:
                logger.warn(
                    f"Sanity check failed for book {ebook_path} | (Length-Extracted:"
                    f" {len_extracted}, Length-Calibre: {len_calibre})"
                )
            self.book_log_["sanity_check"] = {
                "passed": sanity_check_passed,
                "len_extracted": len_extracted,
                "len_calibre": len_calibre,
            }
        return extracted

    def _extract(
        self,
        ebook: epub.EpubBook,
        ebook_path: Union[str, Path],
        unzipped_dir: Path,
        temporary_content_dir: TemporaryFileStringDir,
    ) -> Dict[str, str]:
        """TODO: docs

        Args:
            ebook (epub.EpubBook): _description_
            ebook_path (Union[str, Path]): _description_

        Returns:
            Dict[str, str]: _description_
        """
        extracted = {
            "title": ebook.title,
            "source": str(ebook_path),
            "processing_log": None,  # Just to keep it first place to debug.
            "epub_metadata": self._exctract_epub_metadata(ebook),
            "content": self._extract_from_toc(
                ebook, unzipped_dir, temporary_content_dir
            ),
        }
        return extracted

    def _exctract_epub_metadata(self, ebook: epub.EpubBook) -> Dict[str, str]:
        """TODO: docs

        Args:
            ebook (epub.EpubBook): _description_

        Returns:
            Dict[str, str]: _description_
        """
        metadata = ebook.metadata
        cleaned_metadata = {}
        for field in metadata.values():
            for field_name, values in field.items():
                values = values[0]
                if values[0] is None:
                    continue
                if not values[-1]:
                    cleaned_metadata[field_name] = values[0]
                else:
                    cleaned_metadata[field_name] = values
        return cleaned_metadata

    def _extract_from_toc(
        self,
        ebook: epub.EpubBook,
        unzipped_dir: Path,
        temporary_content_dir: TemporaryFileStringDir,
    ) -> List[Union[Dict[str, str], List[Dict[str, str]]]]:
        """TODO: docs

        Args:
            ebook (epub.EpubBook): _description_

        Returns:
            List[Union[Dict[str, str], List[Dict[str, str]]]]: _description_
        """
        seen_content = set()

        def _get(toc):
            content = []
            for elem in toc:
                if isinstance(elem, tuple):
                    section, section_content = elem
                    if (
                        section_href_clean := sanitize_href(section.href)
                    ) not in seen_content:
                        content.append(
                            {
                                "type": section.__class__.__name__,
                                "title": section.title,
                                # In RARE cases (looking at you Kastelau )
                                # sections have content themselves!
                                "content": _get([section]) + _get(section_content),
                            }
                        )
                        seen_content.add(section_href_clean)
                else:
                    if (link_clean := sanitize_href(elem.href)) not in seen_content:
                        try:
                            content.append(
                                self._resolve_link(
                                    elem, ebook, unzipped_dir, temporary_content_dir
                                )
                            )
                        except LinkResolveException:
                            pass
                        seen_content.add(link_clean)

            return content

        global_content = _get(ebook.toc)
        return global_content

    def _resolve_link(
        self,
        link: ebooklib.epub.Link,
        ebook: epub.EpubBook,
        unzipped_dir: Path,
        temporary_content_dir: TemporaryFileStringDir,
    ):
        href = link.href
        href_clean = sanitize_href(href)
        html = ebook.get_item_with_href(href)
        found_via_cleaned_href = False
        if html is None:
            html = ebook.get_item_with_href(href_clean)
            found_via_cleaned_href = True
        if html is None:
            html = ebook.get_item_with_href(parse.unquote(href))
        if html is None:
            html = ebook.get_item_with_href(parse.unquote(href_clean))
            found_via_cleaned_href = True
        if html is None:
            msg = f"Could not find resource for href {href} ({href_clean})"
            logger.warning(msg)
            raise LinkResolveException(msg)
        entry = {
            # "type": str(type(html)),
            "type": html.__class__.__name__,
            "href": link.href,
            "href_clean": href_clean,
            "found_via_href_clean": found_via_cleaned_href,
            "title": link.title,
            "html_title": self._get_html_title(html),
            "body_titles": self._get_html_body_titles(html),
            "text": self._extract_html(html, unzipped_dir, temporary_content_dir),
            "images": self._find_images(html, unzipped_dir=unzipped_dir),
        }
        return entry

    def _html2tei(self, temporary_content_dir: TemporaryFileStringDir) -> None:
        with tempfile.TemporaryDirectory() as converted_content_dir:
            converted_content_dir = Path(converted_content_dir)

            command = [
                "java",
                "-jar",
                SAXON_PATH.absolute(),
                f"-s:{temporary_content_dir.path.absolute()}",
                f"-xsl:{self.HTML2TEI_XSLT_STYLESHEET_PATH}",
                f"-o:{converted_content_dir.absolute()}",
            ]
            # DEBUG
            # command = [
            #     "cp",
            #     "-a",
            #     f"{temporary_content_dir.path.absolute()}/.",
            #     str(converted_content_dir.absolute())
            # ]
            #
            try:
                _ = subprocess.run(command, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                raise SaxonException(e.stderr.decode("utf-8"))

            pp_error_already_raised = False
            for converted_file in converted_content_dir.glob("*"):
                filename = converted_file.stem
                tei_xml = converted_file.read_text()
                try:
                    tei_xml = self.tei_postprocessor(tei_xml=tei_xml)
                except Exception as e:
                    if not pp_error_already_raised:
                        logger.exception(
                            "Applying XSLT post-processing steps to extracted TEI"
                            " content failed"
                        )
                        pp_error_already_raised = True
                    else:
                        ...
                temporary_content_dir.index[filename].update(tei_xml)

    # TODO: Move to utils?
    def _parse_xml(self, xml_file: Union[str, Path]) -> et._ElementTree:
        """Parses an xml-file mercifully.

        Args:
            xml_file (Union[str, Path]): Path to file

        Returns:
            et._ElementTree: Parsed content
        """
        if isinstance(xml_file, Path):
            xml_file = str(xml_file)
        parser = et.XMLParser(recover=True, resolve_entities=False)
        tree = et.parse(xml_file, parser)
        return tree

    def _get_opf_spine_content(self, opf_doc: et._ElementTree) -> List[str]:
        """Parses the spine *.opf file and returns a list of (href-)referenced files.

        Args:
            opf_doc (et._ElementTree): Parsed *.opf file

        Returns:
            List[str]: List of referenced files.
        """
        opf_manifest_items = opf_doc.xpath(
            "//opf:manifest//opf:item", namespaces=XML_NAMESPACES
        )
        opf_spine_entries = opf_doc.xpath(
            "//opf:spine//opf:itemref", namespaces=XML_NAMESPACES
        )
        opf_spine_content = []
        for itemref in opf_spine_entries:
            idref = itemref.xpath("./@idref", namespaces=XML_NAMESPACES)[0]
            referenced_file = opf_doc.xpath(
                f"//opf:manifest//opf:item[@id = '{idref}']",
                namespaces=XML_NAMESPACES,
            )[0].xpath("./@href")[0]
            opf_spine_content.append(referenced_file)
        # TODO Watch me:
        opf_spine_content = [
            i.split("#")[0] if "#" in i else i for i in opf_spine_content
        ]
        return opf_spine_content

    def _get_ncx_content(self, ncx_doc: et._ElementTree) -> Tuple[List[str], List[str]]:
        """Parses navpoints in an *.ncx-file and returns a list of referenced documents.
        TODO: ncx_referenced_uids are currently unused and could be discarded?

        Args:
            ncx_doc (et._ElementTree): Parsed *.ncx-file

        Returns:
            Tuple[List[str], List[str]]: List of referenced files, List of referenced UIDs.
        """
        ncx_navpoints = ncx_doc.xpath("//ncx:navPoint", namespaces=XML_NAMESPACES)
        ncx_referenced_content = [
            i.xpath("./ncx:content/@src", namespaces=XML_NAMESPACES)[0]
            for i in ncx_navpoints
        ]
        ncx_referenced_content = [
            i.split("#")[0] if "#" in i else i for i in ncx_referenced_content
        ]
        ncx_referenced_uids = ncx_doc.xpath(
            "//ncx:navPoint/@id", namespaces=XML_NAMESPACES
        )
        return ncx_referenced_content, ncx_referenced_uids

    def _sanitize_toc(
        self,
        ebook: epub.EpubBook,
        unzipped_dir: Path,
    ) -> epub.EpubBook:
        """Injects missing files into the TOC-structure of an EpubBook object.
        To do so, the content of the *.opf file of a book is parsed and files that occur in this file
        but are not referenced in the TOC are inserted into the TOC.
        To find the correct index of the newly injected files some hard-coded rules are used.
        If a new file in inserted into the toc its file content is appended to the epub.EpubBook's content.

        Args:
            ebook (epub.EpubBook): Object of the parsed ebook
            unzipped_dir (Path): Path to the unzipped ebook's content

        Returns:
            _type_: The ebook with sanitized TOC attribute
        """

        try:
            opf_file = list(unzipped_dir.glob("**/*.opf"))[0]
            ncx_file = list(unzipped_dir.glob("**/*.ncx"))[0]
        except IndexError:
            # Let's try proceeding!
            logger.warning("Could not find opf or ncx file.")
            self.book_log_["toc_repair"] = " ".join(str(IndexError).split())
            return ebook

        # Parse both files
        opf_doc = self._parse_xml(opf_file)
        ncx_doc = self._parse_xml(ncx_file)

        # Get contents of both files
        opf_referenced_content = self._get_opf_spine_content(opf_doc)
        ncx_referenced_content, ncx_referenced_uids = self._get_ncx_content(ncx_doc)
        differences = [
            i for i in opf_referenced_content if i not in ncx_referenced_content
        ]
        # import pudb; pu.db
        # print(differences)

        if not differences:
            if self.verbose:
                logger.info("OPF and NCX are aligned, no further steps needed")
            self.book_log_["toc_repair"] = False
            return ebook

        if self.verbose:
            logger.info("Trying to align TOC with OPF content")
        self.book_log_["toc_repair"] = True
        if isinstance(ebook.toc, list):
            toc = MultiLevelList(ebook.toc.copy())
        else:
            logger.info(f"Found toc of type {type(ebook.toc)}. Wrapped it in list.")
            toc = MultiLevelList([ebook.toc])
        last_href = None
        for href in opf_referenced_content:
            opf_href_index = get_href_index(toc, href, multiple_matches=False)
            if opf_href_index is None:
                # Insert in first place
                if last_href is None:
                    content = self._create_epub_html(opf_file, href)
                    ebook.items.append(content)
                    toc.insert(0, epub.Link(href=href, title=content.title))
                else:
                    content = self._create_epub_html(opf_file, href)
                    ebook.items.append(content)
                    new_elem_index = get_href_index(
                        toc, last_href, multiple_matches=False
                    )
                    # Set index for new elem
                    new_elem_index[-1] += 1
                    # Check if new index is valid.
                    # If the new index is invalid,
                    # we assume the new element has to be added to the end of the TOC.
                    append = False
                    try:
                        toc[new_elem_index]
                    except IndexError:
                        # list.insert adds to end if index is larger than list...
                        # so we'll use the largest integer possible as index...
                        # this is easier than inferring the length of the sublist
                        # in a multi-level-list to use len(sublist)
                        new_elem_index[-1] = MAX_INT
                        append = True

                    # TODO Keep this just in case the while-loop shows to be harmful
                    # if isinstance(toc[new_elem_index], epub.Section):
                    #     new_elem_index[-1] = 1
                    #     new_elem_index += [0]
                    if not append:
                        while isinstance(
                            toc[new_elem_index], epub.Section
                        ) or isinstance(toc[new_elem_index], (tuple, list)):
                            if isinstance(toc[new_elem_index], epub.Section):
                                # If new index points to a section we re-route it to the first element of the section's content
                                new_elem_index[-1] = 1
                                new_elem_index += [0]
                            if isinstance(toc[new_elem_index], tuple):
                                # If it points a tuple containing a (Section, [Section content, ...]), we also re-route it the the content
                                new_elem_index += [1, 0]
                            if isinstance(toc[new_elem_index], list):
                                # Very rarely we encounter a section with sub-sections as children.
                                # These subsections are wrapped in a list.
                                # To re-route, we leverage the while-loop, and simply re-route the first child section,
                                # and leave the rest to the other rules.
                                new_elem_index += [0]

                    toc.insert(
                        new_elem_index, epub.Link(href=href, title=content.title)
                    )

            last_href = href
        ebook.toc = list(toc)
        return ebook

    @staticmethod
    def _create_epub_html(opf_file: Path, href: str) -> epub.EpubHtml:
        """Creates a new epub_html file containing some newly inserted content.

        Args:
            opf_file (Path): Path to the book's *.opf-file
            href (str): Reference to the new content.

        Returns:
            epub.EpubHtml: The file's epub.EpubHtml representation.
        """
        content = epub.EpubHtml()
        # TODO Refactor sanitize href or make this a new function
        path = Path(opf_file.parent / parse.unquote(href))
        html = path.read_bytes()
        content.content = html
        soup = BeautifulSoup(html.decode("utf-8"), "html.parser")
        title_elem = soup.find("title")
        title = title_elem.string if title_elem is not None else None
        content.title = title
        content.href = href
        return content

    @staticmethod
    def href_in_toc(href, unraveled_toc) -> Union[None, int]:
        """TODO: docs

        Args:
            href (_type_): _description_
            unraveled_toc (_type_): _description_

        Returns:
            Union[None, int]: _description_
        """
        for index, entry in enumerate(unraveled_toc):
            elem = entry[-1]
            if elem.href == href:
                return index
        return None

    def _extract_html(
        self,
        html: epub.EpubHtml,
        unzipped_dir: Path,
        temporary_content_dir: TemporaryFileStringDir,
    ) -> TemporaryFileString:
        html = css2inline(html=html, unzipped_dir=unzipped_dir)

        # TEI-C Stylesheet delete text content inside in <a>-tags.
        # This will leads to some books totally failing.
        # This is a sub-ideal solution!
        html = re.sub("<a.+?>", "", html)
        html = re.sub("<\/a>", "", html)

        html = html2xml(html)
        file_string = temporary_content_dir.create_file_string(html)
        return file_string

    def _find_images(
        self, html: epub.EpubHtml, unzipped_dir: Path
    ) -> Union[List[str], None]:
        """TODO: docs

        Args:
            html (epub.EpubHtml): _description_

        Returns:
            Union[List[str], None]: _description_
        """
        soup = BeautifulSoup(html.content.decode("utf-8"), "html.parser")
        image_tags = soup.findAll("img")
        if not self.include_images:
            images = [tag["src"] for tag in image_tags]
        else:
            images = []
            for tag in image_tags:
                path = Path(tag["src"])
                filename = path.name
                path = get_location(filename, unzipped_dir)
                try:
                    image = Image.from_path(path)
                except Exception as e:
                    logger.warning(f"Could not locate image. {e}")
                    continue
                image.path = str(path.relative_to(unzipped_dir))
                images.append(image)
        if not images:
            return None
        return images

    def _get_html_title(self, html: epub.EpubHtml) -> Union[str, None]:
        """TODO: docs

        Args:
            html (epub.EpubHtml): _description_

        Returns:
            Union[str, None]: _description_
        """
        soup = BeautifulSoup(html.content.decode("utf-8"), "html.parser")
        title = soup.find("title")
        if title:
            if title.string is not None and title.string.strip():
                return title.string
        else:
            return None

    def _get_html_body_titles(self, html: epub.EpubHtml) -> Union[List[str], None]:
        """TODO: docs

        Args:
            html (epub.EpubHtml): _description_

        Returns:
            Union[List[str], None]: _description_
        """
        soup = BeautifulSoup(html.content.decode("utf-8"), "html.parser")
        h_tags = soup.find_all([f"h{i}" for i in range(1, 6)])
        headings = []
        for h_tag in h_tags:
            if h_tag.string is not None and h_tag.string.strip():
                headings.append(h_tag.string)
        if headings:
            return headings
        else:
            return None

    def _sanity_check(
        self, extracted: dict, ebook_path: Union[str, Path]
    ) -> Tuple[bool, int, int]:
        """Compare the extracted content to the txt version of the epub (created using calibre)

        Args:
            extracted (dict): Extracted ebook data
            ebook_path (Union[str, Path]): Path to the epub

        Returns:
            bool: True if the content are identical
        """

        def remove_tags(html: str) -> str:
            return re.sub(r"<.*?>", "", html)

        # TODO move to utils?
        def normalize_string(string: str) -> str:
            string = html.unescape(string)
            string = remove_tags(string)
            string = " ".join(string.split())
            return string

        # 1. Get calibre txt content of book
        with tempfile.NamedTemporaryFile("r", suffix=".txt") as output_file:
            calibre_convert(ebook_path, output_file.name)
            output_file.seek(0)
            calibre_content = normalize_string(output_file.read())

        # 2. Recurse through the extracted content and get texts
        def get_text(extracted: dict):
            def _recurse(elem):
                if type(elem) is dict:
                    if "text" in elem:
                        yield elem["text"]
                    for v in elem.values():
                        yield from _recurse(v)
                elif type(elem) is list:
                    for entry in elem:
                        yield from _recurse(entry)

            return " ".join(map(lambda ts: ts.data, _recurse(extracted)))

        extracted_content = normalize_string(get_text(extracted))

        if self.debug:
            check_dir = Path("sanity_check_debug")

            book_dir = ebook_path.name

            final_dir = check_dir / book_dir
            final_dir.mkdir(exist_ok=True, parents=True)

            (final_dir / "calibre.txt").write_text(calibre_content)
            (final_dir / "extracted.txt").write_text(extracted_content)

        SanityCheckOutput = namedtuple(
            "SanityCheckOutput", ["passed_sanity_check", "len_extracted", "len_calibre"]
        )
        return SanityCheckOutput(
            calibre_content == extracted_content,
            len(extracted_content),
            len(calibre_content),
        )

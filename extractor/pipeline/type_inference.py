import logging
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, Generator, List, Optional

from .base import BaseContentPipelineComponent

logger = logging.getLogger(__name__)


class TitleBasedTypeInference(BaseContentPipelineComponent):
    ADDED_FIELDS = ["inferred-type", "processing_log.is_collection"]
    CUSTOM_DESCRIPTION = {
        "description": (
            "Use hard-coded rules to infer section types based in their titles."
        )
    }

    def process(self, extracted: OrderedDict, file_path: Path) -> OrderedDict:
        extracted = super().process(extracted, file_path=file_path)
        # After the content is handled,
        # check if multiple fields are labelled as novels
        # and mark novels as collections
        collection = is_collection(extracted)
        extracted["processing_log"]["is_collection"] = collection
        return extracted

    def process_html(self, html_elem: OrderedDict, file_path: Path) -> None:
        title = html_elem.get("title")
        if title is None:
            title = ""
        title = title.lower()
        href = Path(html_elem["href_clean"].lower()).name

        inferred_type = None

        # BEGIN RULES

        if (
            href == "volume.xhtml"
            or "folge" in title
            and re.search(r"\d+", title) is not None
            or last_word_is(html_elem["text"], word="ende")
        ):
            inferred_type = "novel"
        if "cover" in title or "cover" in href:
            inferred_type = "cover"
        if "rearnotes" in href:
            inferred_type = "endnotes"
        if title.startswith("nr") or "titel" in title:
            inferred_type = "title"
        if title == "einleitung":
            inferred_type = "introduction"
        if title in ("zwischenspiel", "interludium"):
            inferred_type = "interlude"
        if "prolog" in title:
            inferred_type = "prologue"
        if title == "vorwort":
            inferred_type = "foreword"
        if "leseprobe" in title or "leseempfehlungen" in title:
            inferred_type = "reading-sample"
        if title == "unknown":
            inferred_type = "cover"
        if title in ("vorspann", "vorspiel") or href == "preface.xhtml":
            inferred_type = "prelude"
        if title in ("schluss", "epilog", "schluß", "nachspiel") or "epilog" in title:
            inferred_type = "epilogue"
        if title == "nachwort":
            inferred_type = "afterword"
        if title == "Die Hauptpersonen des Romans".lower():
            inferred_type = "cast-list"
        if "impressum" in title:
            inferred_type = "imprint"
        if (
            "inhaltsverzeichnis" in title
            or "inhalt" in title
            or "inhaltsübersicht" in title
            or href == "toc.xhtml"
        ):
            inferred_type = "toc"
        if title in (
            "anzeige",
            "die pr-produktpalette",
            "neu im pr-universum?",
            "gespannt darauf, wie es weitergeht?",
        ):
            inferred_type = "advertisement"
        if (
            re.search(r"\d+\.", title) is not None
            or "kapitel" in title
            or all([c.isnumeric() for c in set(title)])
        ):
            inferred_type = "chapter"
        if title == "häufig gestellte fragen":
            inferred_type = "faq"
        if title == "feedback" or "feedback" in href:
            inferred_type = "feedback"
        if title == "vorschau":
            inferred_type = "preview"
        if title == "wasserzeichen-hinweis":
            inferred_type = "copyright-statement"
        if title == "widmung":
            inferred_type = "dedication"
        if "autor" in title:
            inferred_type = "author-information"
        if title in (
            "ein kleines who's who des perry rhodan-universums",
            "die welt des perry rhodan",
        ):
            inferred_type = "lore"

        # END RULES

        if inferred_type is None:
            logger.warning(f"No rule for title '{title}' of EPubHtml.")
            inferred_type = "unknown"

        html_elem["inferred-type"] = inferred_type
        html_elem.move_to_end("text")

    def process_section(self, section: OrderedDict, file_path: Path) -> None:
        title = section.get("title", "").lower()
        if not title:
            inferred_type = "unknown"
        elif title.strip().startswith("nr."):
            inferred_type = "novel"
        elif title == "häufig gestellte fragen":
            inferred_type = "faq"
        elif title in (
            "ein kleines who's who des perry rhodan-universums",
            "die welt des perry rhodan",
        ):
            inferred_type = "lore"
        elif title in (
            "anzeige",
            "die pr-produktpalette",
            "neu im pr-universum?",
            "gespannt darauf, wie es weitergeht?",
        ):
            inferred_type = "advertisement"
        elif "leseprobe" in title:
            inferred_type = "reading-sample"
        elif check_if_novel(section):
            inferred_type = "novel"
        else:
            logger.warning(f"No rule for title {title} of section.")
            inferred_type = "unknown"

        section["inferred-type"] = inferred_type
        section.move_to_end("content")


def check_if_novel(section: OrderedDict) -> bool:
    """Checks if the entries of a section have titles containing the string and if they are consecutively numbered.
    If both requirements are met, the section is likely to be a novel.

    Args:
        section (OrderedDict): Section content

    Returns:
        bool: True if likely to be a novel
    """
    content = section["content"]
    reduced_titles = get_chapter_titles([entry["title"] for entry in content])
    return reduced_titles == list(sorted(reduced_titles, key=chapter_sort_key))


def get_chapter_titles(titles: List[str]) -> List[str]:
    reduced_content = []
    for title in titles:
        if title is None:
            continue
        title = title.lower()
        if re.search(r"\d+", title) is not None and "kapitel" in title:
            reduced_content.append(title)
    return reduced_content


def chapter_sort_key(chapter: str) -> int:
    return int(re.search(r"\d+", chapter).group(0))


def remove_markup(string: str) -> str:
    return re.sub(r"<[^<]+>", "", str(string))


def only_alpha(string: str) -> str:
    return "".join([c for c in str(string) if c.isalpha() or c.isspace()])


def last_word_is(string: str, word: str) -> bool:
    string = "".join(only_alpha(remove_markup(string)).lower().split())
    return string[-len(word) :] == word.lower()


def is_collection(extracted: Dict, key: Optional[str] = None) -> bool:
    if key is None:
        key = "inferred-type"

    def _recurse(elem):
        if elem.get(key, "") == "novel":
            yield True
        if (content := elem.get("content")) is not None:
            for child in content:
                yield from _recurse(child)

    return sum(_recurse(extracted)) > 1

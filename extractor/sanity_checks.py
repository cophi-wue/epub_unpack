import re
from typing import Dict, Generator, List


def contains_duplicate_texts(extracted: Dict) -> bool:
    """Checks if the extracted ebook contains text field with similar content.

    Args:
        extracted (Dict): Dictionary with extracted epubs

    Returns:
        bool: True if extracted ebook contains duplicate texts, else False
    """

    def gather_texts(extracted: Dict) -> Generator[str, None, None]:
        for name, field in extracted.items():
            if name == "text" and (content := extracted[name]) is not None:
                if isinstance(content, list):
                    yield "\n".join(content)
                else:
                    yield content
            if isinstance(field, dict):
                yield from gather_texts(field)
            if isinstance(field, list):
                for entry in field:
                    if isinstance(entry, dict):
                        yield from gather_texts(entry)

    texts = [text for text in gather_texts(extracted) if text.strip()]
    # ONLY for manual debugging
    # if len(texts) != len(set(texts)):
    #     from collections import Counter

    #     newline = lambda: "\n"
    #     logger.critical(
    #         f"\n{newline().join(text for text, count in Counter(texts).most_common() if count > 1)}\n"
    #     )
    return len(texts) != len(set(texts))


def chapters_are_consecutive(extracted: Dict) -> bool:
    """(Naive) function to check if chapter appearing in an extracted book are consecutive.

    TODO: FAILS IF TWO BOOKS ARE ON THE SAME CONTENT LEVEL IN A SAMMELBAND (1, ..., 9, 1, ..., 7)

    Args:
        extracted (Dict): Extracted ebook

    Returns:
        bool: True if chapter numbers are consecutive
    """

    def gather_content_titles(extracted: Dict) -> Generator[List[str], None, None]:
        for name, field in extracted.items():
            if name == "content":
                yield [
                    entry.get("title", entry.get("toc_title", None)) for entry in field
                ]
                for entry in field:
                    if "content" in entry:
                        yield from gather_content_titles(entry)

    def reduce_to_chapter_titles(content: List[str]) -> List[str]:
        reduced_content = []
        for title in content:
            if title is None:
                continue
            title = title.lower()
            if re.search(r"\d+", title) is not None and "kapitel" in title:
                reduced_content.append(title)
        return reduced_content

    def chapter_sort_key(chapter: str) -> int:
        return int(re.search(r"\d+", chapter).group(0))

    all_chapters = [
        reduce_to_chapter_titles(d) for d in gather_content_titles(extracted)
    ]
    for chapters in all_chapters:
        if chapters != list(sorted(chapters, key=chapter_sort_key)):
            return False
    return True

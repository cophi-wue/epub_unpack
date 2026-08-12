from __future__ import annotations

import re
from base64 import b64decode, b64encode
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union


@dataclass
class Image:
    path: str
    content: str

    def __post_init__(self):
        self.path = str(self.path)

    @classmethod
    def from_path(cls, path: Union[str, Path]) -> Image:
        encoded_content = b64encode(Path(path).read_bytes()).decode("utf-8")
        return cls(path=path, content=encoded_content)

    def write_to_dir(self, directory: Union[str, Path]) -> Path:
        directory = Path(directory)
        if directory.is_file() and directory.exists():
            raise ValueError("directory has to point to a (non-existing) directory.")
        directory.mkdir(exist_ok=True, parents=True)
        path = Path(self.path)
        filename = path.name
        out_path = directory / filename
        out_path.write_bytes(b64decode(self.content))
        return out_path


def extract_images(extracted: dict, image_dir: Path) -> None:
    def _recurse(elem: Union[OrderedDict, List]):
        if isinstance(elem, list):
            for e in elem:
                _recurse(e)
        elif elem["type"] == "Section":
            for elem in elem["content"]:
                _recurse(elem)
        elif elem["type"] == "EpubHtml":
            image_paths = []
            if (images := elem.pop("images", None)) is not None:
                image_dir.mkdir(exist_ok=True, parents=True)
                for image in images:
                    image_new_path = image.write_to_dir(image_dir)
                    image_new_path = image_new_path.relative_to(image_dir.parent)
                    filename = image_new_path.name
                    image_new_path = str(image_new_path)
                    image_paths.append(image_new_path)
                    if text := elem.get("text", ""):
                        # Use regex to overwrite old path to ensure that relative paths are also overwritten.
                        regex_filename = re.escape(filename)
                        text = re.sub(
                            rf'<graphic url=".+?{regex_filename}"',
                            f'<graphic url="{image_new_path}"',
                            str(text),
                        )
                        elem["text"] = text
                elem["images"] = image_paths

    _recurse(extracted["content"])

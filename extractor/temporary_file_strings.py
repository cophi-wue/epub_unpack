from __future__ import annotations

import errno
import shutil
import tempfile
from collections import UserString
from pathlib import Path
from typing import Dict, Optional


class TemporaryFileString(UserString):
    def __init__(
        self,
        seq: object,
        parent: Optional[TemporaryFileStringDir] = None,
        suffix: Optional[str] = None,
    ):
        super().__init__(seq)
        if parent is not None:
            self.parent = parent
        else:
            self.parent = TemporaryFileStringDir()
        self.suffix = suffix
        self._realize()

    def _allocate(self):
        self.file_path: Path = (
            self.parent.path / f"{str(hash(self))}{self.suffix if self.suffix else ''}"
        )

    def _write(self):
        self.file_path.write_text(self.data)

    def _realize(self):
        self._allocate()
        self._write()

    def update(self, new_content: str):
        self.data = new_content
        self._write()

    def __hash__(self) -> int:
        return hash(self.data)

    def __str__(self):
        return self.data


class TemporaryFileStringDir:
    def __init__(self) -> None:
        self.dir: str = tempfile.mkdtemp()
        self.path: Path = Path(self.dir)
        self.index: Dict[str, TemporaryFileString] = {}

    def __del__(self):
        self.delete()

    def delete(self):
        try:
            shutil.rmtree(self.dir)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
        self.index.clear()

    def create_file_string(
        self, string: str, suffix: Optional[str] = None
    ) -> TemporaryFileString:
        file_string = TemporaryFileString(string, parent=self, suffix=suffix)
        self.index[file_string.file_path.stem] = file_string
        return file_string


if __name__ == "__main__":
    string_dir = TemporaryFileStringDir()
    string = string_dir.create_file_string("Hello World")
    print(string.file_path)
    print(Path(string.file_path).read_text())
    print(id(string))

    #################

    string.update("Hallo Welt!")
    print(string.file_path)
    print(Path(string.file_path).read_text())
    print(id(string))

    # string_dir.delete()
    # print(string.file_path)
    # print(Path(string.file_path).read_text())
    # print(id(string))

    import json

    json.dumps(string)

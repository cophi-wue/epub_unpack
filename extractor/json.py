import json
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import asdict as dataclass_asdict
from dataclasses import is_dataclass
from pathlib import Path
from typing import Any, Dict, Union

from .temporary_file_strings import TemporaryFileString


class EPubUnpackJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, TemporaryFileString):
            return o.data
        if is_dataclass(o):
            return dataclass_asdict(o)

        return super().default(o)


def read_json(path: Union[str, Path]) -> OrderedDict:
    path = Path(path)
    return json.loads(path.read_text(), object_pairs_hook=OrderedDict)


def write_json(data: Dict, path: Union[str, Path]) -> None:
    path = Path(path)
    path.write_text(json.dumps(data, indent=4, cls=EPubUnpackJSONEncoder))

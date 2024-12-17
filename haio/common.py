from icecream import ic
from typing import Any
import json
import hashlib


def help() -> None:
    print("HumanAI.io")


check_frequency = 5


def haio_hash(src: Any) -> str:
    return hashlib.md5(json.dumps(src, sort_keys=True).encode()).hexdigest()
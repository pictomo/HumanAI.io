from icecream import ic
from typing import Any
import json
import hashlib
import uuid
import base64


def help() -> None:
    print("HumanAI.io")


check_frequency = 5


def haio_hash(src: Any) -> str:
    return hashlib.md5(json.dumps(src, sort_keys=True).encode()).hexdigest()


def haio_uid() -> str:
    return str(uuid.uuid4())


def img_path_to_url(img_path: str, mime_type: str) -> str:
    try:
        if mime_type not in ["image/jpeg", "image/png"]:
            raise ValueError(f"Unsupported mime_type: {mime_type}")
        with open(img_path, "rb") as image_file:
            base64_encoded = base64.b64encode(image_file.read()).decode("utf-8")
        data_url = f"data:{mime_type};base64,{base64_encoded}"
        return data_url
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {img_path}")
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")

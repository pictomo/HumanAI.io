from icecream import ic
from typing import Any, Tuple
import base64
import hashlib
import json
import uuid


def help() -> None:
    print("HumanAI.io")


check_frequency = 5


def haio_hash(src: Any) -> str:
    return hashlib.md5(json.dumps(src, sort_keys=True).encode()).hexdigest()


def haio_uid() -> str:
    return str(uuid.uuid4())


def img_to_url(img_data: bytes, mime_type: str) -> str:
    try:
        if mime_type not in {"image/jpeg", "image/png", "image/gif", "image/webp"}:
            raise ValueError(f"Unsupported mime_type: {mime_type}")

        # バイナリデータをBase64にエンコード
        base64_encoded = base64.b64encode(img_data).decode("utf-8")

        # 埋め込みURLを作成
        data_url = f"data:{mime_type};base64,{base64_encoded}"
        return data_url
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


def img_path_to_url(img_path: str, mime_type: str) -> str:
    try:
        with open(img_path, "rb") as image_file:
            return img_to_url(image_file.read(), mime_type)
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {img_path}")
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")


def data_url_to_img(url: str) -> Tuple[str, bytes]:
    try:
        if not url.startswith("data:"):
            raise ValueError("URL must start with 'data:'.")

        metadata, img_data_str = url[5:].split(",", 1)

        if not metadata.endswith(";base64"):
            raise ValueError("Data URL must end with ';base64'.")

        mime_type = metadata.split(";", 1)[0]

        valid_mime_types = {"image/png", "image/jpeg", "image/gif", "image/webp"}
        if mime_type not in valid_mime_types:
            raise ValueError(f"Unsupported MIME type: {mime_type}")

        try:
            img_data = base64.b64decode(img_data_str)
        except:
            raise ValueError(f"Failed to decode Base64 data")

        return mime_type, img_data
    except Exception as e:
        raise RuntimeError(f"An error occurred: {e}")

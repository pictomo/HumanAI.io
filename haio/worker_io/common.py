from PIL import Image
import difflib
import io


def resize_image(
    img_data: bytes,
    mime_type: str,
    max_width: int | None = None,
    max_height: int | None = None,
    min_width: int = 0,
    min_height: int = 0,
) -> bytes:
    try:
        # バイナリデータを画像として読み込む
        img: Image.Image = Image.open(io.BytesIO(img_data))
    except Exception as e:
        raise ValueError("Invalid image data provided.") from e

    # 元のサイズを取得
    original_width, original_height = img.size
    new_width, new_height = original_width, original_height

    # 最大サイズのチェック
    if max_width is not None or max_height is not None:
        fixed_max_width: float = max_width if max_width is not None else float("inf")
        fixed_max_height: float = max_height if max_height is not None else float("inf")

        # 最大サイズを考慮したアスペクト比維持のリサイズ
        if original_width > fixed_max_width or original_height > fixed_max_height:
            scale_width = fixed_max_width / original_width
            scale_height = fixed_max_height / original_height
            scale = min(scale_width, scale_height)  # 縮小率を決定
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)

    # 最小サイズのチェック
    if new_width < min_width or new_height < min_height:
        if new_width == 0 or new_height == 0:
            raise ValueError(
                "The calculated dimensions are invalid (zero width/height)."
            )
        scale_width = min_width / new_width
        scale_height = min_height / new_height
        scale = max(scale_width, scale_height)  # 拡大率を決定
        new_width = int(new_width * scale)
        new_height = int(new_height * scale)

    # リサイズを実行
    img = img.resize((new_width, new_height))

    # リサイズ後の画像をバイナリに変換
    output = io.BytesIO()
    img_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/gif": "GIF",
        "image/webp": "WEBP",
    }.get(mime_type, None)
    if img_format is None:
        raise ValueError("Unsupported mime_type: {mime_type}")
    img.save(output, format=img_format)
    output.seek(0)

    return output.getvalue()


def force_choice(input_str: str, options: list[str]) -> str:
    input_str = str(input_str)
    # force AI output to be enum value
    if not options:
        raise ValueError("The options list cannot be empty.")

    closest_match = difflib.get_close_matches(input_str, options, n=1)

    return closest_match[0] if closest_match else options[0]

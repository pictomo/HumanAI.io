from haio import img_to_url, resize_image
import pyperclip
import os
import sys


if __name__ == "__main__":
    # 画像の相対パスを絶対パスに変換
    relative_path = "img/4_pixel.png"
    mime_type = "image/png"
    absolute_path = os.path.join(
        os.path.dirname(os.path.abspath(sys.argv[0])), relative_path
    )

    # 画像ファイルを読み込み
    with open(absolute_path, "rb") as f:
        img_data = f.read()

    # 画像のリサイズ
    resized_img_data = resize_image(
        img_data=img_data,
        mime_type=mime_type,
        max_width=70,  # 最大幅を指定
        max_height=70,  # 最大高さを指定
    )

    # リサイズした画像を埋め込み URL に変換
    url = img_to_url(img_data=resized_img_data, mime_type=mime_type)

    # 結果を出力
    print(url[:50] + "...")

    # クリップボードにコピー
    pyperclip.copy(url)

    # chromeだと一定サイズ以上の画像について白飛びする可能性あり
    # 大きすぎるとURLとして不正になる可能性あり

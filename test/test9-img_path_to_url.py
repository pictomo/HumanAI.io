from haio import img_path_to_url
import pyperclip
import os, sys

relative_path = "img/cactus.jpg"
absolute_path = os.path.join(
    os.path.dirname(os.path.abspath(sys.argv[0])), relative_path
)
url = img_path_to_url(img_path=absolute_path, mime_type="image/jpeg")
print(url[:50] + "...")

pyperclip.copy(url)

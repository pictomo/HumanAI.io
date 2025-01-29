from icecream import ic
from dotenv import load_dotenv
import os
import textwrap
import httpx
import base64
import google.generativeai as genai

from haio.common import haio_hash
from haio.types import QuestionConfig, Answer
from haio.worker_io.types import Worker_IO


class Gemini_IO(Worker_IO):
    def __init__(self) -> None:
        load_dotenv()
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        self.gemini_client = genai.GenerativeModel("gemini-1.5-flash-latest")
        self.asked: dict[str, Answer] = {}

    def ask(self, question_config: QuestionConfig) -> str:
        question_config_hash = haio_hash(question_config)

        # GEMINI_IOでは、回答を取得せずに同じ質問を複数回聞くことはできない
        # 既に質問済みならエラーを返す
        if question_config_hash in self.asked:
            raise Exception("already asking")

        # システムメッセージの初期化
        system_message: str = textwrap.dedent(
            """\
            You will be given the same questions given to humans.
            Questions are in Markdown format.
            Answer accurately and concisely, following the answer format below.
            Only write your answer; no explanations, semicolons, etc. are needed.
            answer format: """
        )

        # 回答形式クエリの初期化
        generation_config: genai.GenerationConfig

        # 回答形式に応じてシステムメッセージとクエリを構築
        if question_config["answer"]["type"] == "number":
            system_message += "number"
            generation_config = genai.GenerationConfig(
                response_mime_type="application/json", response_schema=float
            )
        elif question_config["answer"]["type"] == "text":
            system_message += "string"
            generation_config = genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=str,
            )
        elif question_config["answer"]["type"] == "select":
            system_message += "select from {}".format(
                question_config["answer"]["options"]
            )
            generation_config = genai.GenerationConfig(
                response_mime_type="text/x.enum",
                response_schema={
                    "type": "STRING",
                    "enum": question_config["answer"]["options"],
                },
            )
        else:
            raise Exception("Invalid answer type.")

        # questionのテンプレートを構成
        user_content: str | list
        user_message = ""
        img_urls: list[str] = []
        for question in question_config["question"]:
            match question["tag"]:
                case "h1":
                    user_message += f"# {question['value']}\n"
                case "h2":
                    user_message += f"## {question['value']}\n"
                case "h3":
                    user_message += f"### {question['value']}\n"
                case "h4":
                    user_message += f"#### {question['value']}\n"
                case "h5":
                    user_message += f"##### {question['value']}\n"
                case "h6":
                    user_message += f"###### {question['value']}\n"
                case "p":
                    user_message += f"{question['value']}\n"
                case "img":
                    img_urls.append(question["src"])
                case _:
                    raise Exception("Invalid tag.")

        if img_urls:
            user_content = [system_message]
            for img_url in img_urls:
                if img_url.startswith("data:"):
                    metadata, img_data_base64 = img_url[5:].split(",", 1)
                    mime_type = metadata.split(";", 1)[0]
                else:
                    image_response = httpx.get(img_url)
                    mime_type = image_response.headers.get("Content-Type")
                    img_data_base64 = base64.b64encode(image_response.content).decode(
                        "utf-8"
                    )

                user_content.append(
                    {
                        "mime_type": mime_type,
                        "data": img_data_base64,
                    }
                )
            user_content.append(user_message)
        else:
            user_content = system_message + "\n" + user_message

        # タスクの構成と発行
        response = self.gemini_client.generate_content(
            contents=user_content,
            generation_config=generation_config,
        )
        print("Gemini Question Config Hash:", question_config_hash)

        if response.text:
            answer_objstr = response.text
            self.asked[question_config_hash] = answer_objstr
        else:
            raise Exception("The model returned empty response.")

        return question_config_hash

    def is_finished(self, id: str) -> bool:
        # idはquestion_config_hash
        if id not in self.asked:
            raise Exception("never asked")
        return self.asked[id] != ""  # 実質的には常にTrue

    def get_answer(self, id: str) -> Answer:
        # idはquestion_config_hash
        if id not in self.asked:
            raise Exception("never asked")
        tmp = self.asked[id]
        self.asked[id] = ""
        self.asked.pop(id)
        return tmp

    async def ask_get_answer(self, question_config: QuestionConfig) -> Answer:
        id = self.ask(question_config=question_config)
        return self.get_answer(id)

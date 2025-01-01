from icecream import ic
from typing import Union, Any
from dotenv import load_dotenv
import json
import textwrap
from openai import OpenAI

from haio.common import haio_hash
from haio.types import QuestionConfig
from haio.worker_io.types import Worker_IO


class OpenAI_IO(Worker_IO):
    def __init__(self) -> None:
        load_dotenv()
        self.openai_client = OpenAI()
        self.asked: dict[str, str] = {}

    def ask(self, question_config: QuestionConfig) -> str:
        question_config_hash = haio_hash(question_config)

        # OpenAI_IOでは、回答を取得せずに同じ質問を複数回聞くことはできない
        # 既に質問済みならエラーを返す
        if question_config_hash in self.asked:
            raise Exception("already asking")

        # questionのテンプレートを構成
        user_content: Union[str, list]
        user_message = ""
        imgs: list[str] = []
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
                    imgs.append(question["src"])
                case _:
                    raise Exception("Invalid tag.")

        if imgs:
            user_content = [{"type": "text", "text": user_message}]
            for img in imgs:
                user_content.append({"type": "image_url", "image_url": {"url": img}})
        else:
            user_content = user_message

        # システムメッセージの初期化
        system_message: str = textwrap.dedent(
            """\
            Respond to questions in Markdown format in the same way as a crowdsourcing worker would, providing accurate and concise answers according to the answer format below.
            Write only the answer and no explanation, semicolon, etc. is needed.
            You do not need to rely on crowdworkers for the accuracy of your answers, so please provide answers of the highest possible standard.
            answer format: """
        )

        # 回答形式のクエリの初期化
        response_format: Any = {
            "type": "json_schema",
            "json_schema": {
                "name": "answer",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"answer": {}},
                    "required": ["answer"],
                    "additionalProperties": False,
                },
            },
        }

        # 回答形式に応じてシステムメッセージと回答形式を構築
        if question_config["answer"]["type"] == "number":
            system_message += "{{answer: {}}}".format("number")
            response_format["json_schema"]["schema"]["properties"]["answer"][
                "type"
            ] = "number"
        elif question_config["answer"]["type"] == "text":
            system_message += "{{answer: {}}}".format("string")
            response_format["json_schema"]["schema"]["properties"]["answer"][
                "type"
            ] = "string"
        elif question_config["answer"]["type"] == "select":
            system_message += "{{answer: select from {}}}".format(
                question_config["answer"]["options"]
            )
            response_format["json_schema"]["schema"]["properties"]["answer"][
                "type"
            ] = "string"
            response_format["json_schema"]["schema"]["properties"]["answer"]["enum"] = (
                question_config["answer"]["options"]
            )
        else:
            raise Exception("Invalid answer type.")

        # タスクの構成と発行
        completion = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_content},
            ],
            response_format=response_format,
        )
        print("OpenAI Question Config Hash:", question_config_hash)

        if completion.choices[0].message.content:
            answer_objstr = completion.choices[0].message.content
            self.asked[question_config_hash] = json.loads(answer_objstr)["answer"]
        else:
            raise Exception("The model returned empty response.")

        return question_config_hash

    def is_finished(self, id: str) -> bool:
        # idはquestion_config_hash
        if id not in self.asked:
            raise Exception("never asked")
        return self.asked[id] != ""  # 実質的には常にTrue

    def get_answer(self, id: str) -> str:
        # idはquestion_config_hash
        if id not in self.asked:
            raise Exception("never asked")
        tmp = self.asked[id]
        self.asked[id] = ""
        self.asked.pop(id)
        return tmp

    async def ask_get_answer(self, question_config: QuestionConfig) -> str:
        id = self.ask(question_config=question_config)
        return self.get_answer(id)

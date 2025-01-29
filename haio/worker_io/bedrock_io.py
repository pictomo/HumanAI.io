from dotenv import load_dotenv
from icecream import ic
from typing import cast
import boto3
import httpx
import os
import textwrap

from haio.common import haio_hash, data_url_to_img
from haio.types import QuestionConfig, MutableAnswer, Answer
from haio.worker_io.common import resize_image, force_choice
from haio.worker_io.types import Worker_IO


class Bedrock_IO(Worker_IO):
    model_list = {
        "us.meta.llama3-2-90b-instruct-v1:0": {
            "can_force_tool_use": False
        },  # Multiple image inputs are not supported.
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0": {"can_force_tool_use": True},
        "us.amazon.nova-lite-v1:0": {"can_force_tool_use": False},
    }

    def __init__(self, model_id: str) -> None:
        if model_id not in self.model_list:
            raise Exception("Invalid or Unsupported model_id.")
        load_dotenv()
        self.client = boto3.client(
            service_name="bedrock-runtime",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name="us-east-1",
        )
        self.model_id = model_id
        self.asked: dict[str, Answer] = {}

    def ask(self, question_config: QuestionConfig) -> str:
        question_config_hash = haio_hash(question_config)

        # 回答を取得せずに同じ質問を複数回聞くことはできない
        # 既に質問済みならエラーを返す
        if question_config_hash in self.asked:
            raise Exception("already asking")

        tool_name = "AnswerDisplay"

        # システムメッセージの初期化
        system_message: str = textwrap.dedent(
            """\
            You will be given the same questions given to humans.
            Questions are in Markdown format.
            Answer accurately and concisely, following the answer format below.
            Only write your answer; no explanations, semicolons, etc. are needed.
            Make sure to use the tool {tool_name} to answer.
            answer format: """
        )

        # 回答形式クエリの初期化
        output_json_schema: dict = {
            "type": "object",
            "properties": {
                "answer": {},
            },
            "required": ["answer"],
        }

        # 回答形式に応じてシステムメッセージとクエリを構築
        if question_config["answer"]["type"] == "number":
            system_message += "number"
            output_json_schema["properties"]["answer"] = {"type": "number"}
        elif question_config["answer"]["type"] == "text":
            system_message += "string"
            output_json_schema["properties"]["answer"] = {"type": "string"}
        elif question_config["answer"]["type"] == "select":
            system_message += "select from {}".format(
                question_config["answer"]["options"]
            )
            output_json_schema["properties"]["answer"] = {
                "type": "string",
                "enum": question_config["answer"]["options"],
            }
        else:
            raise Exception("Invalid answer type.")

        # configures the tool
        tool_definition = {
            "toolSpec": {
                "name": tool_name,
                "description": "Takes structured input and displays it to the user.",
                "inputSchema": {
                    "json": output_json_schema,
                },
            }
        }
        tool_config: dict[str, dict | list] = {"tools": [tool_definition]}
        if self.model_list[self.model_id]["can_force_tool_use"]:
            tool_config["toolChoice"] = {
                "tool": {
                    "name": tool_name,
                },
            }

        # questionのテンプレートを構成
        user_content: list
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

        user_content = []
        for img_url in img_urls:
            if img_url.startswith("data:"):
                mime_type, img_data = data_url_to_img(img_url)
            else:
                image = httpx.get(img_url)
                mime_type = image.headers.get("Content-Type")
                img_data = image.content
            img_data = resize_image(
                img_data,
                mime_type,
                max_width=1120,
                max_height=1120,
                min_width=32,
                min_height=32,
            )
            # https://www.reddit.com/r/LocalLLaMA/comments/1frwnpj/llama_32_vision_model_image_pixel_limitations/
            # llama3-2-90b-instruct-v1 image pixel limitations
            format = {
                "image/png": "png",
                "image/jpeg": "jpeg",
                "image/jpg": "jpeg",  # 一部システムではjpgとして扱われるため
                "image/gif": "gif",
                "image/webp": "webp",
            }.get(mime_type, None)
            if format is None:
                raise Exception("Invalid image format.")
            user_content.append(
                {
                    "image": {
                        "format": format,
                        "source": {"bytes": img_data},
                    }
                }
            )
        user_content.append({"text": user_message})

        # タスクの構成と発行
        response = self.client.converse(
            modelId=self.model_id,
            messages=[
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            system=[
                {
                    "text": system_message,
                }
            ],
            toolConfig=tool_config,
        )
        print("Bedrock Question Config Hash:", question_config_hash)

        response_content = response["output"]["message"]["content"]
        tool_use_response = next(
            (item for item in response_content if "toolUse" in item), None
        )
        text_response = next(
            (item for item in response_content if "text" in item), None
        )

        if tool_use_response is not None:
            answer_obj = tool_use_response["toolUse"]["input"]
            answer = answer_obj["answer"]
        elif text_response is not None:
            answer = text_response["text"]
        else:
            raise Exception("The model returned empty response.")

        if cast(MutableAnswer, question_config["answer"])["type"] == "select":
            formatted_answer = force_choice(
                answer, cast(MutableAnswer, question_config["answer"])["options"]
            )
            self.asked[question_config_hash] = formatted_answer
        elif cast(MutableAnswer, question_config["answer"])["type"] == "number":
            self.asked[question_config_hash] = str(float(answer))
        else:
            self.asked[question_config_hash] = answer

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

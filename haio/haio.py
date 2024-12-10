from icecream import ic
from typing import TypedDict, Any
from dotenv import load_dotenv
import os
import xml.etree.ElementTree as ET
import json
import asyncio
import textwrap
import boto3
from openai import OpenAI
from bs4 import BeautifulSoup


load_dotenv()


def help() -> None:
    print("HumanAI.io")


class QuestionConfig(TypedDict):
    title: str
    description: str
    question: list
    answer: dict


def insert_data(question_config: QuestionConfig, data_list: list) -> QuestionConfig:
    question_config_copy = question_config.copy()
    for i in range(len(question_config_copy["question"])):
        if type(question_config_copy["question"][i]["value"]) == int:
            question_config_copy["question"][i]["value"] = data_list[
                question_config_copy["question"][i]["value"]
            ]
    if type(question_config_copy["answer"]["type"]) in ["int", "text"]:
        if type(question_config_copy["answer"]["value"]) == int:
            question_config_copy["answer"]["value"] = data_list[
                question_config_copy["answer"]["value"]
            ]
        elif type(question_config_copy["answer"]["type"]) == "select":
            for i in range(len(question_config_copy["answer"]["options"])):
                if type(question_config_copy["answer"]["options"][i]) == int:
                    question_config_copy["answer"]["options"][i] = data_list[
                        question_config_copy["answer"]["options"][i]
                    ]
    return question_config_copy


class OpenAI_IO:
    openai_client = OpenAI()
    answer = ""

    def ask(self, question_config: QuestionConfig, data_list: list) -> None:
        if self.answer != "":
            raise Exception("already asking")

        # question_configのデータ挿入
        question_config = insert_data(
            question_config=question_config, data_list=data_list
        )

        # questionのテンプレートを構成
        user_message = ""
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
                case _:
                    raise Exception("Invalid tag.")

        # answerのテンプレートを構成

        # システムメッセージの初期化
        system_message: Any = textwrap.dedent(
            """\
            Respond to questions in Markdown format in the same way as a crowdsourcing worker would, providing accurate and concise answers according to the answer format below.
            Write only the answer and no explanation, semicolon, etc. is needed.
            You do not need to rely on crowdworkers for the accuracy of your answers, so please provide answers of the highest possible standard.
            answer format: """
        )

        # クエリの初期化
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

        # 回答形式に応じてシステムメッセージとクエリを構築
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
                {"role": "user", "content": user_message},
            ],
            response_format=response_format,
        )

        if completion.choices[0].message.content:
            answer_objstr = completion.choices[0].message.content
            self.answer = json.loads(answer_objstr)["answer"]
        else:
            raise Exception("The model returned empty response.")

    def is_finished(self) -> bool:
        if self.answer == "":
            raise Exception("never asked")
        return self.answer != ""

    def get_answer(self) -> str:
        if self.answer == "":
            raise Exception("never asked")
        tmp = self.answer
        self.answer = ""
        return tmp

    async def ask_get_answer(
        self, question_config: QuestionConfig, data_list: list
    ) -> str:
        self.ask(question_config=question_config, data_list=data_list)
        return self.get_answer()


# template1: str = textwrap.dedent("""\
# <HTMLQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2011-11-11/HTMLQuestion.xsd">
#     <HTMLContent><![CDATA[

#     <!DOCTYPE html>
#     <html>
#         <head>
#             <meta http-equiv='Content-Type' content='text/html; charset=UTF-8'/>
#             <script type='text/javascript' src='https://s3.amazonaws.com/mturk-public/externalHIT_v1.js'></script>
#         </head>
#         <body>
#             <center>
#                 <form name='mturk_form' method='post' id='mturk_form' action='https://www.mturk.com/mturk/externalSubmit'>
#                     <h2>{question}</h2>
#                     <p><input type='text' name='response'/></p>
#                     <p><input type='submit' id='submitButton' value='Submit' /></p>
#                     <input type='hidden' value='' name='assignmentId' id='assignmentId'/>
#                 </form>
#             </center>
#             <script language='Javascript'>turkSetAssignmentID();</script>
#         </body>
#     </html>

#     ]]>
#     </HTMLContent>
#     <FrameHeight>800</FrameHeight>
# </HTMLQuestion>
# """)

# https://requester.mturk.com/create/projects/new collect utterance
template2: str = textwrap.dedent(
    """\
<HTMLQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2011-11-11/HTMLQuestion.xsd">
    <HTMLContent><![CDATA[
        <!DOCTYPE html>
            <body>
                <script src="https://assets.crowd.aws/crowd-html-elements.js"></script>
                <crowd-form answer-format="flatten-objects">
                    {body}
                </crowd-form>
            </body>
        </html>
    ]]></HTMLContent>
    <FrameHeight>0</FrameHeight>
</HTMLQuestion>
"""
)


class MTurk_IO:
    mturk_client = boto3.client(
        "mturk",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
        endpoint_url="https://mturk-requester-sandbox.us-east-1.amazonaws.com",
    )
    hit_id: str = ""

    def test(self) -> dict:
        return self.mturk_client.get_account_balance()

    # HITを作成し、そのHIT IDを返す
    def ask(self, question_config: QuestionConfig, data_list: list) -> None:
        if self.hit_id != "":
            raise Exception("already asking")

        # question_configのデータ挿入
        question_config = insert_data(
            question_config=question_config, data_list=data_list
        )

        # テンプレートの構成
        soup = BeautifulSoup("", "html.parser")

        # questionのテンプレートを構成
        for question in question_config["question"]:
            if question["tag"] in ["h1", "h2", "h3", "h4", "h5", "h6", "p"]:
                input_soup = soup.new_tag(question["tag"])
                input_soup.string = question["value"]
                soup.append(input_soup)
            else:
                raise Exception("Invalid tag.")

        # answerのテンプレートを構成
        if question_config["answer"]["type"] in ["text", "number"]:
            output_soup = soup.new_tag(
                name="crowd-input",
                attrs={
                    "name": "response",
                    "placeholder": "Type your answer here...",
                    "required": "",
                },
            )
            soup.append(output_soup)
        elif question_config["answer"]["type"] == "select":
            output_soup = soup.new_tag(name="select", attrs={"name": "response"})
            for option in question_config["answer"]["options"]:
                option_soup = soup.new_tag(name="option", attrs={"value": option})
                option_soup.string = option
                output_soup.append(option_soup)
            soup.append(output_soup)
        else:
            raise Exception("Invalid answer type.")

        # タスクの構成と発行
        res = self.mturk_client.create_hit(
            Title=question_config["title"],
            Description=question_config["description"],
            Keywords="this,is,my,HIT,hoge",  # コンマ区切りで検索キーワードを指定
            Reward="0.05",
            MaxAssignments=1,  # 受け付ける回答数（＝ワーカー数）上限
            LifetimeInSeconds=3600,  # 有効期限
            AssignmentDurationInSeconds=300,  # 制限時間
            Question=template2.format(
                body=soup.prettify()
            ),  # my_hit.htmlの中身を文字列でそのまま渡す
        )

        print("HIT ID:", res["HIT"]["HITId"])
        self.hit_id = res["HIT"]["HITId"]

    # HIT IDを指定して、そのHITが終了しているかどうかを返す
    def is_finished(self, hit_id: str | None = None) -> bool:
        if self.hit_id == "":
            raise Exception("never asked")

        hit_id = hit_id or self.hit_id
        res = self.mturk_client.get_hit(HITId=hit_id)
        state = res["HIT"]["HITStatus"]
        return state == "Reviewable" or state == "Reviewing"

    # HIT IDを指定して、そのHITの結果を返す
    def get_answer(self, hit_id: str | None = None) -> str:
        if self.hit_id == "":
            raise Exception("never asked")

        hit_id = hit_id or self.hit_id
        res: dict = self.mturk_client.list_assignments_for_hit(HITId=hit_id)
        self.hit_id = ""
        answer = res["Assignments"][0]["Answer"]
        root = ET.fromstring(answer)
        node = root.find(
            ".//ns:FreeText",
            {
                "ns": "http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2005-10-01/QuestionFormAnswers.xsd"
            },
        )
        if node is None:
            raise Exception("The answer was not found.")
        free_text: str = node.text or ""
        return free_text

    # HITを作成し、その結果を返す
    async def ask_get_answer(
        self, question_config: QuestionConfig, data_list: list
    ) -> str:
        self.ask(question_config=question_config, data_list=data_list)
        while not self.is_finished():
            await asyncio.sleep(10)
        return self.get_answer()

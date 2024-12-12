from icecream import ic
from typing import TypedDict, Literal, Union, Any
from dotenv import load_dotenv
import sys
import os
import copy
import xml.etree.ElementTree as ET
import json
import asyncio
import textwrap
import hashlib
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


class QuestionTemplate(TypedDict):
    title: str
    description: str
    question: list
    answer: dict


DataList = list[str]


class OpenAI_IO:
    def __init__(self) -> None:
        self.openai_client = OpenAI()
        self.asked: dict[str, str] = {}

    def ask(self, question_config: QuestionConfig) -> str:
        question_config_hash = haio_hash(question_config)

        # OpenAI_IOでは、回答を取得せずに同じ質問を複数回聞くことはできない
        # 既に質問済みならエラーを返す
        if question_config_hash in self.asked:
            raise Exception("already asking")

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
        system_message: str = textwrap.dedent(
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
    def __init__(self) -> None:
        self.mturk_client = boto3.client(
            "mturk",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name="us-east-1",
            endpoint_url="https://mturk-requester-sandbox.us-east-1.amazonaws.com",
        )
        self.asked: list[str] = []

    def test(self) -> dict:
        return self.mturk_client.get_account_balance()

    # HITを作成し、そのHIT IDを返す
    def ask(self, question_config: QuestionConfig) -> str:

        # MTurk_IOでは、全く同じ質問を複数回聞ける
        # # 既に質問済みならエラーを返す
        # if self.hit_id != "":
        #     raise Exception("already asking")

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
        self.asked.append(res["HIT"]["HITId"])
        return res["HIT"]["HITId"]

    # HIT IDを指定して、そのHITが終了しているかどうかを返す
    def is_finished(self, id: str) -> bool:
        # idはHIT ID
        if id not in self.asked:
            raise Exception("never asked")

        res = self.mturk_client.get_hit(HITId=id)
        state = res["HIT"]["HITStatus"]
        return state == "Reviewable" or state == "Reviewing"

    # HIT IDを指定して、そのHITの結果を返す
    def get_answer(self, id: str) -> str:
        # idはHIT ID
        if id not in self.asked:
            raise Exception("never asked")

        res: dict = self.mturk_client.list_assignments_for_hit(HITId=id)
        if id in self.asked:
            self.asked.remove(id)
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
    async def ask_get_answer(self, question_config: QuestionConfig) -> str:
        id = self.ask(question_config=question_config)
        while not self.is_finished(id=id):
            await asyncio.sleep(10)
        return self.get_answer(id=id)


def haio_hash(src: Any) -> str:
    return hashlib.md5(json.dumps(src, sort_keys=True).encode()).hexdigest()


class AskedQuestion(TypedDict):
    question_template: QuestionConfig
    data_list: DataList


class CacheInfo(TypedDict):
    cache_file_path: str
    answer: Union[str, None]


def insert_data(
    question_template: QuestionTemplate, data_list: DataList
) -> QuestionConfig:
    question_config = copy.deepcopy(question_template)
    for i in range(len(question_config["question"])):
        if type(question_config["question"][i]["value"]) == int:
            question_config["question"][i]["value"] = data_list[
                question_config["question"][i]["value"]
            ]
    if type(question_config["answer"]["type"]) in ["int", "text"]:
        if type(question_config["answer"]["value"]) == int:
            question_config["answer"]["value"] = data_list[
                question_config["answer"]["value"]
            ]
        elif type(question_config["answer"]["type"]) == "select":
            for i in range(len(question_config["answer"]["options"])):
                if type(question_config["answer"]["options"][i]) == int:
                    question_config["answer"]["options"][i] = data_list[
                        question_config["answer"]["options"][i]
                    ]
    return question_config


class HAIOClient:
    def __init__(self, humna_client: MTurk_IO, ai_client: OpenAI_IO) -> None:
        self.human_client = humna_client
        self.ai_client = ai_client

    def get_cache_dir_path(self) -> str:
        # haio_cacheディレクトリのパスを取得
        executed_script_path = os.path.abspath(sys.argv[0])
        executed_script_dir = os.path.dirname(executed_script_path)
        cache_dir = os.path.join(executed_script_dir, "haio_cache")

        # haio_cacheディレクトリが存在しない場合は作成
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)

        return cache_dir

    def get_cache_file_path(self, question_template: QuestionTemplate) -> str:
        # haio_cacheディレクトリのパスを取得
        cache_dir_path = self.get_cache_dir_path()

        # question_templateをハッシュ化
        question_template_hash = haio_hash(question_template)

        # question_templateに対するキャッシュファイルが存在するか確認、なければ作成
        cache_file_path = os.path.join(cache_dir_path, question_template_hash)
        if not os.path.exists(cache_file_path):
            with open(cache_file_path, "w") as f:
                json.dump({"question_template": question_template, "data_lists": {}}, f)

        return cache_file_path

    def check_cache(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        client: Literal["human", "ai"],
    ) -> CacheInfo:

        data_list_hash = haio_hash(data_list)

        cache_file_path = self.get_cache_file_path(question_template)

        with open(cache_file_path, "r") as f:
            cache = json.load(f)
        # データに対する回答格納場所が存在するか確認、なければ作成
        data_list_cache = cache["data_lists"].get(data_list_hash, None)
        if data_list_cache is None:
            cache["data_lists"][data_list_hash] = {
                "data_list": data_list,
                "answer_list": [],
            }
            with open(cache_file_path, "w") as f:
                json.dump(cache, f)
        else:
            # 想定するクライアントの回答が存在するか確認、あればそれを返し、なければ何もしない
            answer_cache = next(
                (
                    item
                    for item in data_list_cache["answer_list"]
                    if item["client"] == client
                ),
                None,
            )
            if answer_cache is not None:
                return {
                    "cache_file_path": cache_file_path,
                    "answer": answer_cache["answer"],
                }

        return {
            "cache_file_path": cache_file_path,
            "answer": None,
        }

    def add_cache(
        self,
        cache_file_path: str,
        data_list: DataList,
        client: Literal["human", "ai"],
        answer: str,
    ):
        with open(cache_file_path, "r") as f:
            cache = json.load(f)
        cache["data_lists"][haio_hash(data_list)]["answer_list"].append(
            {"client": client, "answer": answer}
        )
        with open(cache_file_path, "w") as f:
            json.dump(cache, f)

    async def ask_get_answer(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        client: Literal["human", "ai"],
    ) -> str:

        # キャッシュの確認とパスの取得、キャッシュがあれば返す
        cache_info = self.check_cache(
            question_template=question_template, data_list=data_list, client=client
        )
        if cache_info["answer"] is not None:
            return cache_info["answer"]

        question_config = insert_data(
            question_template=question_template, data_list=data_list
        )

        if client == "human":
            answer = await self.human_client.ask_get_answer(
                question_config=question_config
            )
        elif client == "ai":
            answer = await self.ai_client.ask_get_answer(
                question_config=question_config
            )
        else:
            raise Exception("Invalid client.")

        # キャッシュファイルに回答を追加

        self.add_cache(
            cache_file_path=cache_info["cache_file_path"],
            data_list=data_list,
            client=client,
            answer=answer,
        )

        return answer

    def ask(
        self, question_template: QuestionTemplate, data_list: DataList
    ) -> AskedQuestion:
        return {"question_template": question_template, "data_list": data_list}

    async def wait(
        self, asked_questions: Union[AskedQuestion, list[AskedQuestion]]
    ) -> Union[str, list[str]]:
        if isinstance(asked_questions, dict):
            # 単一問題に対して回答を取得
            return await self.ask_get_answer(
                question_template=asked_questions["question_template"],
                data_list=asked_questions["data_list"],
                client="human",
            )

        elif isinstance(asked_questions, list):

            # asked_questionsが全て同じquestion_templateであるか確認
            question_template = asked_questions[0]["question_template"]
            for asked_question in asked_questions:
                if asked_question["question_template"] != question_template:
                    raise Exception(
                        "Multiple question_templates are mixed. It can only be same question_template in a list."
                    )

            # 一斉に回答を取得

            answer_list: list[Union[str, None]] = []
            question_id_list: dict[str, dict] = {}
            for i in range(len(asked_questions)):
                cache = self.check_cache(
                    question_template=asked_questions[i]["question_template"],
                    data_list=asked_questions[i]["data_list"],
                    client="human",
                )
                cache_answer = cache["answer"]
                cache_file_path = cache["cache_file_path"]
                if cache_answer is None:
                    question_config = insert_data(
                        question_template=asked_questions[i]["question_template"],
                        data_list=asked_questions[i]["data_list"],
                    )
                    hit_id = self.human_client.ask(question_config=question_config)
                    question_id_list[hit_id] = {
                        "index": i,
                        "data_list": asked_questions[i]["data_list"],
                    }
                    answer_list.append(None)
                else:
                    answer_list.append(cache_answer)
            # この時点で、answer_listはキャッシュが存在する場合は回答、存在しない場合はNoneが入っている
            while question_id_list:
                for hit_id in list(question_id_list.keys()):
                    if self.human_client.is_finished(hit_id):
                        answer = self.human_client.get_answer(hit_id)
                        answer_list[question_id_list[hit_id]["index"]] = answer
                        self.add_cache(
                            cache_file_path=cache_file_path,
                            data_list=question_id_list[hit_id]["data_list"],
                            client="human",
                            answer=answer,
                        )
                        question_id_list.pop(hit_id)
                await asyncio.sleep(10)

            return answer_list

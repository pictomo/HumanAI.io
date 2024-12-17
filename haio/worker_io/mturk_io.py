from icecream import ic
from dotenv import load_dotenv
import os
import xml.etree.ElementTree as ET
import asyncio
import textwrap
import boto3
from bs4 import BeautifulSoup

from haio.common import check_frequency
from haio.types import QuestionConfig
from haio.worker_io.types import Worker_IO


load_dotenv()


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


class MTurk_IO(Worker_IO):
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
            elif question["tag"] == "img":
                input_soup = soup.new_tag(name="img", attrs={"src": question["src"]})
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
            await asyncio.sleep(check_frequency)
        return self.get_answer(id=id)

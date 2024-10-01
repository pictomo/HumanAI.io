from openai import OpenAI
import boto3
from dotenv import load_dotenv
import os
import time
import xml.etree.ElementTree as ET

load_dotenv()


def help() -> None:
    print("HumanAI.io")


class OpenAI_IO:
    openai_client = OpenAI()

    def question(self, question: str) -> str:
        completion = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": question},
            ],
        )

        if completion.choices[0].message.content:
            return completion.choices[0].message.content
        else:
            raise Exception("The model returned empty response.")


template1: str = """
<HTMLQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2011-11-11/HTMLQuestion.xsd">
    <HTMLContent><![CDATA[

    <!DOCTYPE html>
    <html>
        <head>
            <meta http-equiv='Content-Type' content='text/html; charset=UTF-8'/>
            <script type='text/javascript' src='https://s3.amazonaws.com/mturk-public/externalHIT_v1.js'></script>
        </head>
        <body>
            <center>
                <form name='mturk_form' method='post' id='mturk_form' action='https://www.mturk.com/mturk/externalSubmit'>
                    <h2>{question}</h2>
                    <p><input type='text' name='response'/></p>
                    <p><input type='submit' id='submitButton' value='Submit' /></p>
                    <input type='hidden' value='' name='assignmentId' id='assignmentId'/>
                </form>
            </center>
            <script language='Javascript'>turkSetAssignmentID();</script>
        </body>
    </html>

    ]]>
    </HTMLContent>
    <FrameHeight>800</FrameHeight>
</HTMLQuestion>
"""

# https://requester.mturk.com/create/projects/new collect utterance
template2: str = """
<HTMLQuestion xmlns="http://mechanicalturk.amazonaws.com/AWSMechanicalTurkDataSchemas/2011-11-11/HTMLQuestion.xsd">
    <HTMLContent><![CDATA[
        <!DOCTYPE html>
            <body>
                <script src="https://assets.crowd.aws/crowd-html-elements.js"></script>
                <crowd-form answer-format="flatten-objects">

                    <h2>{question}</h2>

                    <crowd-input name="response" placeholder="Type your answer here..." required></crowd-input>
                </crowd-form>
            </body>
        </html>
    ]]></HTMLContent>
    <FrameHeight>0</FrameHeight>
</HTMLQuestion>
"""


class MTurk_IO:
    mturk_client = boto3.client(
        "mturk",
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1",
        endpoint_url="https://mturk-requester-sandbox.us-east-1.amazonaws.com",
    )

    def test(self) -> dict:
        return self.mturk_client.get_account_balance()

    def make_hit(self, question: str) -> str:
        res = self.mturk_client.create_hit(
            Title="Answer a question",
            Description="Please answer the following question simply and accurately.",
            Keywords="this,is,my,HIT,hoge",  # コンマ区切りで検索キーワードを指定
            Reward="0.05",
            MaxAssignments=1,  # 受け付ける回答数（＝ワーカー数）上限
            LifetimeInSeconds=3600,  # HITの有効期限を3600秒（1時間）後に設定
            AssignmentDurationInSeconds=300,  # HITの制限時間を300秒（5分）に設定
            Question=template2.format(
                question=question
            ),  # my_hit.htmlの中身を文字列でそのまま渡す
        )
        print("HIT ID:", res["HIT"]["HITId"])
        return res["HIT"]["HITId"]

    def is_finished(self, hit_id: str) -> bool:
        res = self.mturk_client.get_hit(HITId=hit_id)
        state = res["HIT"]["HITStatus"]
        return state == "Reviewable" or state == "Reviewing"

    def get_result(self, hit_id: str) -> str:
        res: dict = self.mturk_client.list_assignments_for_hit(HITId=hit_id)
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

    def question(self, question: str) -> str:
        hit_id: str = self.make_hit(question)
        while not self.is_finished(hit_id):
            time.sleep(10)
        return self.get_result(hit_id)

from icecream import ic
from typing import overload, TypedDict, Literal
from dotenv import load_dotenv
import sys
import os
import copy
import random
import json
import uuid
import asyncio
from scipy.stats import binomtest

from haio.worker_io.openai_io import OpenAI_IO
from haio.worker_io.mturk_io import MTurk_IO
from .common import check_frequency, haio_hash, haio_uid
from .types import QuestionConfig, QuestionTemplate, DataList, HAIOCache, DataListCache


load_dotenv()


class AskedQuestion(TypedDict):
    question_template: QuestionConfig
    data_list: DataList


class CacheInfo(TypedDict):
    cache_file_path: str
    answer: str | None


def insert_data(
    question_template: QuestionTemplate, data_list: DataList
) -> QuestionConfig:
    question_config = copy.deepcopy(question_template)
    for i in range(len(question_config["question"])):
        if type(question_config["question"][i].get("value", None)) == int:
            question_config["question"][i]["value"] = data_list[
                question_config["question"][i]["value"]
            ]
        if type(question_config["question"][i].get("src", None)) == int:
            question_config["question"][i]["src"] = data_list[
                question_config["question"][i]["src"]
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


ClientType = Literal["human", "ai"]


class HAIOClient:
    def __init__(self, humna_client: MTurk_IO, ai_client: OpenAI_IO) -> None:
        self.human_client = humna_client
        self.ai_client = ai_client

    @overload
    def _get_cache_dir_path(self, ensure_exist: Literal[True] = True) -> str: ...
    @overload
    def _get_cache_dir_path(self, ensure_exist: Literal[False]) -> str | None: ...
    def _get_cache_dir_path(self, ensure_exist=True):
        # haio_cacheディレクトリのパスを取得
        executed_script_path = os.path.abspath(sys.argv[0])
        executed_script_dir = os.path.dirname(executed_script_path)
        cache_dir = os.path.join(executed_script_dir, "haio_cache")

        if not os.path.exists(cache_dir):  # haio_cacheディレクトリが存在しない場合
            if ensure_exist:  # ensure_existがTrueならディレクトリを作成
                os.makedirs(cache_dir)
            else:  # ensure_existがFalseならNoneを返す
                return None

        return cache_dir

    @overload
    def _get_cache_file_path(
        self, question_template: QuestionTemplate, ensure_exist: Literal[True] = True
    ) -> str: ...
    @overload
    def _get_cache_file_path(
        self, question_template: QuestionTemplate, ensure_exist: Literal[False]
    ) -> str | None: ...
    def _get_cache_file_path(self, question_template, ensure_exist=True):
        # haio_cacheディレクトリのパスを取得
        cache_dir_path = self._get_cache_dir_path()

        # question_templateをハッシュ化
        question_template_hash = haio_hash(question_template)

        # question_templateに対するキャッシュファイルが存在するか確認
        cache_file_path = os.path.join(cache_dir_path, question_template_hash)
        if not os.path.exists(cache_file_path):
            if ensure_exist:  # ensure_existがTrueならキャッシュファイルを作成
                with open(cache_file_path, "w") as f:
                    json.dump(
                        {"question_template": question_template, "data_lists": {}}, f
                    )
            else:  # ensure_existがFalseならNoneを返す
                return None

        return cache_file_path

    @overload
    def _get_data_cache_list(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        ensure_exist: Literal[True],
    ) -> DataListCache: ...
    @overload
    def _get_data_cache_list(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        ensure_exist: Literal[False] = False,
    ) -> DataListCache | None: ...
    def _get_data_cache_list(
        self,
        question_template,
        data_list,
        ensure_exist=False,
    ):
        cache_file_path = self._get_cache_file_path(
            question_template=question_template, ensure_exist=ensure_exist
        )
        if cache_file_path is None:
            return None
        with open(cache_file_path, "r") as f:
            cache: HAIOCache = json.load(f)
        data_list_hash = haio_hash(data_list)
        data_list_cache = cache["data_lists"].get(data_list_hash, None)
        if data_list_cache is None:
            if ensure_exist:
                cache["data_lists"][data_list_hash] = {
                    "data_list": data_list,
                    "answer_list": {},
                }
                with open(cache_file_path, "w") as f:
                    json.dump(cache, f)
                data_list_cache = cache["data_lists"][data_list_hash]
            else:
                return None

        return data_list_cache

    def _check_cache(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        client: ClientType,
    ) -> CacheInfo:

        cache_file_path = self._get_cache_file_path(question_template=question_template)
        # データに対する回答格納場所が存在するか確認、なければ作成
        data_list_cache = self._get_data_cache_list(
            question_template=question_template, data_list=data_list, ensure_exist=True
        )
        # 想定するクライアントの回答が存在するか確認、あればそれを返し、なければ何もしない
        answer_cache = next(
            (
                item
                for item in data_list_cache["answer_list"].values()
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

    def _add_cache(
        self,
        cache_file_path: str,
        data_list: DataList,
        client: ClientType,
        answer: str,
    ):
        with open(cache_file_path, "r") as f:
            cache = json.load(f)
        cache["data_lists"][haio_hash(data_list)]["answer_list"][haio_uid()] = {
            "client": client,
            "answer": answer,
        }
        with open(cache_file_path, "w") as f:
            json.dump(cache, f)

    def _ask(self):
        # キャッシュがあれば取得し、なければタスクを投げる
        # タスクを投げる = client.ask()

        pass

    def _get_answer_with_cache(self):
        # 回答を取得し、キャッシュ未追加なら追加する

        pass

    async def ask_get_answer(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        client: ClientType,
    ) -> str:

        # キャッシュの確認とパスの取得、キャッシュがあれば返す
        cache_info = self._check_cache(
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

        self._add_cache(
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

    # asked_questionsが全て同じquestion_templateであるか確認するmethod
    def _check_same_question_template(
        self, asked_questions: list[AskedQuestion]
    ) -> bool:
        question_template = asked_questions[0]["question_template"]
        for asked_question in asked_questions:
            if asked_question["question_template"] != question_template:
                return False
        return True

    # execution methods

    async def _simple_method(
        self, asked_questions: list[AskedQuestion], execution_config: dict
    ) -> list[str]:
        answer_list: list[str, None] = []
        question_id_list: dict[str, dict] = {}

        for i in range(len(asked_questions)):
            cache = self._check_cache(
                question_template=asked_questions[i]["question_template"],
                data_list=asked_questions[i]["data_list"],
                client=execution_config["client"],
            )
            cache_answer = cache["answer"]
            cache_file_path = cache["cache_file_path"]
            if cache_answer is None:
                question_config = insert_data(
                    question_template=asked_questions[i]["question_template"],
                    data_list=asked_questions[i]["data_list"],
                )
                if execution_config["client"] == "ai":
                    asked_id = self.ai_client.ask(question_config=question_config)
                elif execution_config["client"] == "human":
                    asked_id = self.human_client.ask(question_config=question_config)
                question_id_list[asked_id] = {
                    "index": i,
                    "data_list": asked_questions[i]["data_list"],
                }
                answer_list.append(None)
            else:
                answer_list.append(cache_answer)
        # この時点で、answer_listはキャッシュが存在する場合は回答、存在しない場合はNoneが入っている

        if execution_config["client"] == "ai":
            while question_id_list:
                for asked_id in list(question_id_list.keys()):
                    answer = self.ai_client.get_answer(asked_id)
                    answer_list[question_id_list[asked_id]["index"]] = answer
                    self._add_cache(
                        cache_file_path=cache_file_path,
                        data_list=question_id_list[asked_id]["data_list"],
                        client="ai",
                        answer=answer,
                    )
                    question_id_list.pop(asked_id)
        elif execution_config["client"] == "human":
            while question_id_list:
                for asked_id in list(question_id_list.keys()):
                    if self.ai_client.is_finished(asked_id):
                        answer = self.human_client.get_answer(asked_id)
                        answer_list[question_id_list[asked_id]["index"]] = answer
                        self._add_cache(
                            cache_file_path=cache_file_path,
                            data_list=question_id_list[asked_id]["data_list"],
                            client="human",
                            answer=answer,
                        )
                        question_id_list.pop(asked_id)
                await asyncio.sleep(check_frequency)

        return answer_list

    async def _cta_method(
        self, asked_questions, quality_requirement, significance_level
    ) -> list[str]:
        answer_list: list[str | None] = [None] * len(asked_questions)
        human_answer_list: list[str | None] = [None] * len(asked_questions)
        task_clusters: dict[str, list] = {}
        for i, asked_question in enumerate(asked_questions):
            answer = await self.ask_get_answer(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client="ai",
            )
            if answer not in task_clusters:
                if answer not in task_clusters:
                    task_clusters[answer] = []
                task_clusters[answer].append(i)
        indexed_asked_questions = list(enumerate(asked_questions))
        random.shuffle(indexed_asked_questions)
        for i, asked_question in indexed_asked_questions:
            answer = await self.ask_get_answer(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client="human",
            )
            answer_list[i] = answer
            human_answer_list[i] = answer
            for key, task_cluster in task_clusters.items():
                # 統計的検定
                number_of_successes = 0
                number_of_trial = 0
                for j in task_cluster:
                    if human_answer_list[j] != None:
                        number_of_trial += 1
                        if (
                            human_answer_list[j] == key
                        ):  # 本来はkeyでなく、人間ワーカーの多数決
                            number_of_successes += 1
                if number_of_trial == 0:
                    continue
                binomtest_result = binomtest(
                    k=number_of_successes,
                    n=number_of_trial,
                    p=quality_requirement,
                    alternative="greater",
                )
                if binomtest_result.pvalue < significance_level:
                    for task_index in task_cluster:
                        if answer_list[task_index] == None:
                            answer_list[task_index] = (
                                key  # 本来はkeyでなく、人間ワーカーの多数決
                            )
        return answer_list

    async def wait(
        self,
        asked_questions: AskedQuestion | list[AskedQuestion],
        execution_config: dict,
    ) -> str | list[str]:
        if isinstance(asked_questions, dict):
            # 単一問題に対して回答を取得
            return await self.ask_get_answer(
                question_template=asked_questions["question_template"],
                data_list=asked_questions["data_list"],
                client=execution_config["client"],
            )

        elif isinstance(asked_questions, list):

            if execution_config.get("method", None) in ("simple", None):
                # それぞれの問題に対し単純に一度聞いて回答を取得

                clitent_type = execution_config.get("client", None)
                if clitent_type == None:
                    raise Exception("Client is not set.")
                if clitent_type not in ("ai", "human"):
                    raise Exception("Invalid client.")

                if not self._check_same_question_template(asked_questions):
                    raise Exception(
                        "All asked questions must have the same question template."
                    )

                # 一斉に回答を取得

                return await self._simple_method(asked_questions, execution_config)

            elif execution_config["method"] == "cta":
                # CTAによる回答取得

                quality_requirement = execution_config.get("quality_requirement", None)
                if quality_requirement is None:
                    raise Exception("Quality requirement is not set.")
                if not 0 <= quality_requirement <= 1:
                    raise Exception("Invalid quality requirement.")
                if not self._check_same_question_template(asked_questions):
                    raise Exception(
                        "All asked questions must have the same question template."
                    )
                significance_level = execution_config.get("significance_level", 0.05)
                if not 0 <= significance_level <= 1:
                    raise Exception("Invalid significance level.")
                question_template = asked_questions[0]["question_template"]
                if question_template["answer"]["type"] != "select":
                    raise Exception("The answer type must be select.")

                return await self._cta_method(
                    asked_questions=asked_questions,
                    quality_requirement=quality_requirement,
                    significance_level=significance_level,
                )
            else:
                raise Exception("Invalid method.")

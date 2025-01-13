from icecream import ic
from typing import overload, TypedDict, Literal, Tuple
from dotenv import load_dotenv
import sys
import os
import copy
import random
import json
import asyncio
from scipy.stats import binomtest, beta

from haio.worker_io.types import Worker_IO
from haio.worker_io.openai_io import OpenAI_IO
from haio.worker_io.gemini_io import Gemini_IO
from .common import check_frequency, haio_hash, haio_uid
from .types import QuestionConfig, QuestionTemplate, DataList


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


client_types = ["human", "openai", "gemini"]
ClientType = Literal["human", "openai", "gemini"]


class DataListCache(TypedDict):
    data_list: DataList
    answer_list: dict[str, dict]


class HAIOCache(TypedDict):
    question_template: QuestionTemplate
    data_lists: dict[str, DataListCache]


class HAIOClient:
    def __init__(
        self,
        mturk_io: Worker_IO,
        openai_io: OpenAI_IO | None = None,
        gemini_io: Gemini_IO | None = None,
    ) -> None:
        self.human_client = mturk_io

        self.ai_clients: dict[ClientType, Worker_IO] = {}
        if openai_io is not None:
            self.ai_clients["openai"] = openai_io
        if gemini_io is not None:
            self.ai_clients["gemini"] = gemini_io
        # if len(self.ai_clients) == 0:
        #     warnings.warn("No AI client is set.")

        self.used_cache: dict[str, dict[str, set[str]]] = {}

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
    ) -> Tuple[str | None, dict | None]:

        # データに対する回答格納場所が存在するか確認、なければ作成
        data_list_cache = self._get_data_cache_list(
            question_template=question_template, data_list=data_list, ensure_exist=True
        )
        # 想定するクライアントの回答が存在するか確認、あればそれを返し、なければ何もしない
        used_cache_ids = self.used_cache.get(haio_hash(question_template), {}).get(
            haio_hash(data_list), set()
        )
        answer_cache_id, answer_data = next(
            (
                (key, item)
                for key, item in data_list_cache["answer_list"].items()
                if (key not in used_cache_ids and item["client"] == client)
            ),
            (None, None),
        )

        return answer_cache_id, answer_data

    def _add_cache(
        self,
        cache_file_path: str,
        data_list: DataList,
        client: ClientType,
        answer: str,
        cache_id: str | None = None,
    ):
        if cache_id is None:
            cache_id = haio_uid()
        with open(cache_file_path, "r") as f:
            cache = json.load(f)
        cache["data_lists"][haio_hash(data_list)]["answer_list"][cache_id] = {
            "client": client,
            "answer": answer,
        }
        with open(cache_file_path, "w") as f:
            json.dump(cache, f)

    class RequestedQuestion(TypedDict):
        question_template: QuestionTemplate
        data_list: DataList
        cache_id: str
        requested_id: str | None
        client: ClientType

    def _ask(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        client: ClientType,
    ) -> RequestedQuestion:
        # キャッシュがあれば取得し、なければタスクを投げる
        # タスクを投げる = client.ask()

        # キャッシュの有無を確認
        cache_id, _ = self._check_cache(
            question_template=question_template, data_list=data_list, client=client
        )

        # used_cacheに格納場所を確保
        self.used_cache.setdefault(haio_hash(question_template), {})
        self.used_cache[haio_hash(question_template)].setdefault(
            haio_hash(data_list), set()
        )

        requested_id = None
        if cache_id is None:
            cache_id = haio_uid()
            client_entity: Worker_IO
            match client:
                case "human":
                    client_entity = self.human_client
                case "openai":
                    client_entity = self.ai_clients["openai"]
                case "gemini":
                    client_entity = self.ai_clients["gemini"]
                case _:
                    raise Exception("Invalid client.")

            requested_id = client_entity.ask(
                question_config=insert_data(
                    question_template=question_template, data_list=data_list
                )
            )

        self.used_cache[haio_hash(question_template)][haio_hash(data_list)].add(
            cache_id
        )

        return {
            "question_template": question_template,
            "data_list": data_list,
            "cache_id": cache_id,
            "requested_id": requested_id,
            "client": client,
        }

    async def _get_answer(self, requested_question: RequestedQuestion) -> str:
        # 回答を取得し、キャッシュ未追加なら追加する

        if requested_question["requested_id"] is None:
            return self._get_data_cache_list(
                question_template=requested_question["question_template"],
                data_list=requested_question["data_list"],
                ensure_exist=True,
            )["answer_list"][requested_question["cache_id"]]["answer"]

        client_entity: Worker_IO
        match requested_question["client"]:
            case "human":
                client_entity = self.human_client
            case "openai":
                client_entity = self.ai_clients["openai"]
            case "gemini":
                client_entity = self.ai_clients["gemini"]
            case _:
                raise Exception("Invalid client.")

        while not client_entity.is_finished(requested_question["requested_id"]):
            await asyncio.sleep(check_frequency)
        answer = client_entity.get_answer(requested_question["requested_id"])

        self._add_cache(
            cache_file_path=self._get_cache_file_path(
                question_template=requested_question["question_template"]
            ),
            data_list=requested_question["data_list"],
            client=requested_question["client"],
            cache_id=requested_question["cache_id"],
            answer=answer,
        )

        return answer

    async def ask_get_answer(
        self,
        question_template: QuestionTemplate,
        data_list: DataList,
        client: ClientType,
    ) -> str:

        requested_question = self._ask(
            question_template=question_template, data_list=data_list, client=client
        )
        answer = await self._get_answer(requested_question)
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
        answer_list: list[str | None] = []
        requested_questions: list[HAIOClient.RequestedQuestion] = []

        for asked_question in asked_questions:
            requested_question = self._ask(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client=execution_config["client"],
            )
            requested_questions.append(requested_question)
            answer_list.append(None)

        for i, requested_question in enumerate(requested_questions):
            answer = await self._get_answer(requested_question)
            answer_list[i] = answer

        return answer_list

    class TaskCluster(TypedDict):
        task_indexes: set[int]
        answer: str
        client: ClientType
        correct_count: int
        incorrect_count: int

    async def _cta_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        significance_level: float = 0.05,
    ) -> list[str]:
        answer_list: list[str | None] = [None] * len(asked_questions)
        human_answer_list: list[str | None] = [None] * len(asked_questions)
        task_clusters: dict[str, list] = {}
        for i, asked_question in enumerate(asked_questions):
            answer = await self.ask_get_answer(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client="openai",
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

    async def _gta_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        significance_level: float = 0.05,
        iteration: int = 1000,
    ) -> list[str]:
        answer_list: list[str | None] = [None] * len(asked_questions)
        ground_truth_list: list[str | None] = [None] * len(asked_questions)
        unapproved_task_clusters: list[HAIOClient.TaskCluster]
        approved_task_clusters: list[HAIOClient.TaskCluster] = list()

        # make task clusters
        unapproved_task_clusters_dict: dict[str, HAIOClient.TaskCluster] = {}
        for ai_client_name in self.ai_clients.keys():
            for i, asked_question in enumerate(asked_questions):
                answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client=ai_client_name,
                )
                if answer not in unapproved_task_clusters_dict:
                    unapproved_task_clusters_dict[answer] = {
                        "task_indexes": set(),
                        "answer": answer,
                        "client": ai_client_name,
                        "correct_count": 0,
                        "incorrect_count": 0,
                    }
                unapproved_task_clusters_dict[answer]["task_indexes"].add(i)
        unapproved_task_clusters = list(unapproved_task_clusters_dict.values())

        # randomize the order of the tasks, for random sampling
        indexed_asked_questions = list(enumerate(asked_questions))
        random.shuffle(indexed_asked_questions)

        # sampling and approval
        for i, asked_question in indexed_asked_questions:

            # get ground truth (from human here)
            answer = await self.ask_get_answer(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client="human",
            )
            ground_truth_list[i] = answer
            answer_list[i] = answer
            for task_cluster in unapproved_task_clusters + approved_task_clusters:
                if i in task_cluster["task_indexes"]:
                    if task_cluster["answer"] == answer:
                        task_cluster["correct_count"] += 1
                    else:
                        task_cluster["incorrect_count"] += 1

            # check task clusters
            for index, unapproved_task_cluster in enumerate(unapproved_task_clusters):
                # statistical test
                beta_distributions_list: list[list[float]] = []
                for task_cluster in approved_task_clusters + [unapproved_task_cluster]:
                    beta_distributions_list.append(
                        beta.rvs(
                            a=task_cluster["correct_count"] + 1,
                            b=task_cluster["incorrect_count"] + 1,
                            size=iteration,
                        )
                    )
                success_count: int = 0
                for j in range(iteration):
                    numerator: float = 0
                    denominator: int = 0
                    for index, task_cluster in enumerate(
                        approved_task_clusters + [unapproved_task_cluster]
                    ):
                        numerator += beta_distributions_list[index][j] * len(
                            task_cluster["task_indexes"]
                        )
                        denominator += len(task_cluster["task_indexes"])
                    if numerator / denominator >= quality_requirement:
                        success_count += 1

                # task cluster approval
                if 1 - success_count / iteration < significance_level:
                    approved_task_clusters.append(unapproved_task_cluster)
                    unapproved_task_clusters.pop(index)
                    for task_index in unapproved_task_cluster["task_indexes"]:
                        if answer_list[task_index] == None:
                            answer_list[task_index] = unapproved_task_cluster["answer"]

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
                if clitent_type not in client_types:
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
            elif execution_config["method"] == "gta":
                # GTAによる回答取得

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
                iteration = execution_config.get("iteration", 1000)
                if not 0 < iteration:
                    raise Exception("Invalid iteration.")

                question_template = asked_questions[0]["question_template"]
                if question_template["answer"]["type"] != "select":
                    raise Exception("The answer type must be select.")

                return await self._gta_method(
                    asked_questions=asked_questions,
                    quality_requirement=quality_requirement,
                    significance_level=significance_level,
                    iteration=iteration,
                )
            else:
                raise Exception("Invalid method.")

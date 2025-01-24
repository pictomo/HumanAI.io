from dotenv import load_dotenv
from icecream import ic
from scipy.stats import binomtest, beta
from sortedcontainers import SortedDict
from typing import overload, TypedDict, Literal, Tuple, Final
import asyncio
import copy
import json
import os
import random
import sys

from haio.worker_io.types import Worker_IO
from haio.worker_io.bedrock_io import Bedrock_IO
from haio.worker_io.gemini_io import Gemini_IO
from haio.worker_io.openai_io import OpenAI_IO
from .common import check_frequency, haio_hash, haio_uid
from .types import QuestionConfig, QuestionTemplate, DataList, Answer


load_dotenv()


class AskedQuestion(TypedDict):
    question_template: QuestionTemplate
    data_list: DataList


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
    return question_config


client_types = ["human", "openai", "gemini", "llama", "claude"]
ClientType = Literal["human", "openai", "gemini", "llama", "claude"]


class AnswerCache(TypedDict):
    client: ClientType
    answer: Answer


class DataListCache(TypedDict):
    data_list: DataList
    answer_list: dict[str, AnswerCache]


class HAIOCache(TypedDict):
    question_template: QuestionTemplate
    data_lists: dict[str, DataListCache]


class HAIOClient:

    class TaskClusterRequired(TypedDict):
        task_indexes: set[int]
        client: ClientType  # TaskCluser must belong to a single client

    class TaskCluster(TaskClusterRequired, total=False):
        answer: Answer
        approved: bool
        checked: bool
        correct_count: int
        incorrect_count: int

    class MethodStateRequired(TypedDict):
        task_number: int
        task_clusters_dict: dict[str, "HAIOClient.TaskCluster"]
        answer_candidate_lists: dict[ClientType, list[Answer | None]]

    class MethodState(MethodStateRequired, total=False):
        task_phases: SortedDict[int, set[int]]
        question_template: QuestionTemplate
        data_lists: list[DataList | None]

    def __init__(
        self,
        mturk_io: Worker_IO,
        openai_io: OpenAI_IO | None = None,
        gemini_io: Gemini_IO | None = None,
        llama_io: Bedrock_IO | None = None,
        claude_io: Bedrock_IO | None = None,
    ) -> None:
        self.human_client = mturk_io

        self.ai_clients: dict[ClientType, Worker_IO] = {}
        if openai_io is not None:
            self.ai_clients["openai"] = openai_io
        if gemini_io is not None:
            self.ai_clients["gemini"] = gemini_io
        if llama_io is not None:
            self.ai_clients["llama"] = llama_io
        if claude_io is not None:
            self.ai_clients["claude"] = claude_io
        # if len(self.ai_clients) == 0:
        #     warnings.warn("No AI client is set.")

        self.used_cache: dict[str, dict[str, set[str]]] = {}

        # _sequential_cta_1_method state
        self._sequential_cta_1_method_state: dict[str, HAIOClient.MethodState] = {}
        self._sequential_cta_2_method_state: dict[str, HAIOClient.MethodState] = {}
        self._sequential_cta_3_method_state: dict[str, HAIOClient.MethodState] = {}

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
    ) -> Tuple[str | None, AnswerCache | None]:

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
        answer: Answer,
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
            if client == "human":
                client_entity = self.human_client
            elif client in self.ai_clients:
                client_entity = self.ai_clients[client]
            else:
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

    async def _get_answer(self, requested_question: RequestedQuestion) -> Answer:
        # 回答を取得し、キャッシュ未追加なら追加する

        if requested_question["requested_id"] is None:
            return self._get_data_cache_list(
                question_template=requested_question["question_template"],
                data_list=requested_question["data_list"],
                ensure_exist=True,
            )["answer_list"][requested_question["cache_id"]]["answer"]

        client_entity: Worker_IO
        if requested_question["client"] == "human":
            client_entity = self.human_client
        elif requested_question["client"] in self.ai_clients:
            client_entity = self.ai_clients[requested_question["client"]]
        else:
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
    ) -> Answer:

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
    ) -> list[Answer]:
        answer_list: list[Answer | None] = []
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

    async def _cta_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        significance_level: float = 0.05,
    ) -> list[Answer]:
        # prepare
        answer_list: list[Answer | None] = [None] * len(asked_questions)
        answer_candidate_lists: dict[ClientType, list[Answer | None]] = {
            "human": [None] * len(asked_questions)
        }
        for client in self.ai_clients.keys():
            answer_candidate_lists[client] = [None] * len(asked_questions)
        task_clusters: list[HAIOClient.TaskCluster]

        # get answers from AIs and make task clusters
        task_clusters_dict: dict[str | int | float, HAIOClient.TaskCluster] = {}
        for i, asked_question in enumerate(asked_questions):
            for client in self.ai_clients.keys():
                ai_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client=client,
                )

                answer_candidate_lists[client][i] = ai_answer

                task_cluster_id = client + ai_answer
                if task_cluster_id not in task_clusters_dict:
                    task_clusters_dict[task_cluster_id] = {
                        "task_indexes": set(),
                        "client": client,
                        "approved": False,
                        "correct_count": 0,
                        "incorrect_count": 0,
                    }
                task_clusters_dict[task_cluster_id]["task_indexes"].add(i)
        task_clusters = list(task_clusters_dict.values())

        # add given task clusters

        # randomize the order of the tasks, for random sampling
        indexed_asked_questions = list(enumerate(asked_questions))
        random.shuffle(indexed_asked_questions)

        # sampling and approval
        for task_index, asked_question in enumerate(asked_questions):
            if answer_list[task_index] != None:
                continue

            # get ground truth (from human here)
            human_answer = await self.ask_get_answer(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client="human",
            )
            answer_list[task_index] = human_answer
            answer_candidate_lists["human"][task_index] = human_answer
            for task_cluster in task_clusters:
                if (
                    not task_cluster["approved"]
                    and task_index in task_cluster["task_indexes"]
                ):
                    if (
                        answer_candidate_lists[task_cluster["client"]][task_index]
                        == human_answer
                    ):
                        task_cluster["correct_count"] += 1
                    else:
                        task_cluster["incorrect_count"] += 1

                    # check task clusters
                    binomtest_result = binomtest(
                        k=task_cluster["correct_count"],
                        n=task_cluster["correct_count"]
                        + task_cluster["incorrect_count"],
                        p=quality_requirement,
                        alternative="greater",
                    )
                    if binomtest_result.pvalue < significance_level:
                        for inner_task_index in task_cluster["task_indexes"]:
                            if answer_list[inner_task_index] == None:
                                answer_list[inner_task_index] = answer_candidate_lists[
                                    task_cluster["client"]
                                ][inner_task_index]
        return answer_list

    async def _gta_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        significance_level: float = 0.05,
        iteration: int = 1000,
    ) -> list[Answer]:
        answer_list: list[Answer | None] = [None] * len(asked_questions)
        ground_truth_list: list[Answer | None] = [None] * len(asked_questions)
        unapproved_task_clusters: list[HAIOClient.TaskCluster]
        approved_task_clusters: list[HAIOClient.TaskCluster] = list()

        # make task clusters
        unapproved_task_clusters_dict: dict[Answer, HAIOClient.TaskCluster] = {}
        for i, asked_question in enumerate(asked_questions):
            for ai_client_name in self.ai_clients.keys():
                ai_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client=ai_client_name,
                )
                if ai_answer not in unapproved_task_clusters_dict:
                    unapproved_task_clusters_dict[ai_answer] = {
                        "task_indexes": set(),
                        "answer": ai_answer,
                        "client": ai_client_name,
                        "correct_count": 0,
                        "incorrect_count": 0,
                    }
                unapproved_task_clusters_dict[ai_answer]["task_indexes"].add(i)
        unapproved_task_clusters = list(unapproved_task_clusters_dict.values())

        # randomize the order of the tasks, for random sampling
        indexed_asked_questions = list(enumerate(asked_questions))
        random.shuffle(indexed_asked_questions)

        # sampling and approval
        for i, asked_question in indexed_asked_questions:
            if answer_list[i] != None:
                continue

            # get ground truth (from human here)
            human_answer = await self.ask_get_answer(
                question_template=asked_question["question_template"],
                data_list=asked_question["data_list"],
                client="human",
            )
            ground_truth_list[i] = human_answer
            answer_list[i] = human_answer
            for task_cluster in unapproved_task_clusters + approved_task_clusters:
                if i in task_cluster["task_indexes"]:
                    if task_cluster["answer"] == human_answer:
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

    async def _sequential_cta_1_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        significance_level: float = 0.05,
    ) -> list[Answer]:
        # prepare
        state_id = (
            haio_hash(asked_questions[0]["question_template"])
            + ","
            + str(quality_requirement)
            + ","
            + str(significance_level)
        )
        if state_id not in self._sequential_cta_1_method_state:
            self._sequential_cta_1_method_state[state_id] = {
                "task_number": 0,
                "task_clusters_dict": {},
                "answer_candidate_lists": {},
            }
            for client in self.ai_clients.keys():
                self._sequential_cta_1_method_state[state_id]["answer_candidate_lists"][
                    client
                ] = []
        state: Final = self._sequential_cta_1_method_state[state_id]

        answer_list: list[Answer | None] = [None] * len(asked_questions)

        # get each question answer
        for task_index, asked_question in enumerate(asked_questions):

            # get answer from each AI and make task clusters
            for client in self.ai_clients.keys():
                ai_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client=client,
                )
                state["answer_candidate_lists"][client].append(ai_answer)

                task_cluster_id = client + ai_answer
                if task_cluster_id not in state["task_clusters_dict"]:
                    state["task_clusters_dict"][task_cluster_id] = {
                        "task_indexes": set(),
                        "client": client,
                        "approved": False,
                        "correct_count": 0,
                        "incorrect_count": 0,
                    }

                # if task_cluster has approved already, apply the answer
                if (
                    state["task_clusters_dict"][task_cluster_id]["approved"]
                    and answer_list[task_index] == None
                ):
                    answer_list[task_index] = ai_answer
                else:
                    state["task_clusters_dict"][task_cluster_id]["task_indexes"].add(
                        state["task_number"] + task_index
                    )

            # ask human and approve the task clusters
            if answer_list[task_index] == None:
                human_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client="human",
                )
                answer_list[task_index] = human_answer

                # update and approve task clusters
                for task_cluster in state["task_clusters_dict"].values():
                    if (
                        not task_cluster["approved"]
                        and (state["task_number"] + task_index)
                        in task_cluster["task_indexes"]
                    ):
                        if (
                            state["answer_candidate_lists"][task_cluster["client"]][
                                state["task_number"] + task_index
                            ]
                            == human_answer
                        ):
                            task_cluster["correct_count"] += 1
                        else:
                            task_cluster["incorrect_count"] += 1

                        # check task clusters
                        binomtest_result = binomtest(
                            k=task_cluster["correct_count"],
                            n=task_cluster["correct_count"]
                            + task_cluster["incorrect_count"],
                            p=quality_requirement,
                            alternative="greater",
                        )
                        if binomtest_result.pvalue < significance_level:
                            task_cluster["approved"] = True

        state["task_number"] += len(asked_questions)

        return answer_list

    async def _sequential_cta_2_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        sample_size: int,
        significance_level: float = 0.05,
    ) -> list[Answer]:
        # prepare
        state_id = (
            haio_hash(asked_questions[0]["question_template"])
            + ","
            + str(quality_requirement)
            + ","
            + str(significance_level)
            + ","
            + str(sample_size)
        )
        if state_id not in self._sequential_cta_2_method_state:
            self._sequential_cta_2_method_state[state_id] = {
                "task_number": 0,
                "task_clusters_dict": {},
                "answer_candidate_lists": {},
            }
            for client in self.ai_clients.keys():
                self._sequential_cta_2_method_state[state_id]["answer_candidate_lists"][
                    client
                ] = []
        state: Final = self._sequential_cta_2_method_state[state_id]

        answer_list: list[Answer | None] = [None] * len(asked_questions)

        # get each question answer
        for tesk_index, asked_question in enumerate(asked_questions):

            # get answer from each AI and make task clusters
            for client in self.ai_clients.keys():
                ai_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client=client,
                )
                state["answer_candidate_lists"][client].append(ai_answer)

                task_cluster_id = client + ai_answer
                if task_cluster_id not in state["task_clusters_dict"]:
                    state["task_clusters_dict"][task_cluster_id] = {
                        "task_indexes": set(),
                        "client": client,
                        "approved": False,
                        "checked": False,
                        "correct_count": 0,
                        "incorrect_count": 0,
                    }

                # if task_cluster has approved already, apply the answer
                if (
                    state["task_clusters_dict"][task_cluster_id]["approved"]
                    and answer_list[tesk_index] == None
                ):
                    answer_list[tesk_index] = ai_answer
                else:
                    state["task_clusters_dict"][task_cluster_id]["task_indexes"].add(
                        state["task_number"] + tesk_index
                    )

            # ask human
            if answer_list[tesk_index] == None:
                human_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client="human",
                )
                answer_list[tesk_index] = human_answer

                # update task clusters
                for task_cluster in state["task_clusters_dict"].values():
                    if not task_cluster["checked"] and (
                        (state["task_number"] + tesk_index)
                        in task_cluster["task_indexes"]
                    ):
                        if (
                            state["answer_candidate_lists"][task_cluster["client"]][
                                state["task_number"] + tesk_index
                            ]
                            == human_answer
                        ):
                            task_cluster["correct_count"] += 1
                        else:
                            task_cluster["incorrect_count"] += 1

                        # approve task clusters
                        if (
                            task_cluster["correct_count"]
                            + task_cluster["incorrect_count"]
                            >= sample_size
                        ):
                            binomtest_result = binomtest(
                                k=task_cluster["correct_count"],
                                n=task_cluster["correct_count"]
                                + task_cluster["incorrect_count"],
                                p=quality_requirement,
                                alternative="greater",
                            )
                            if binomtest_result.pvalue < significance_level:
                                task_cluster["approved"] = True
                            task_cluster["checked"] = True

        state["task_number"] += len(asked_questions)

        return answer_list

    async def _sequential_cta_3_method(
        self,
        asked_questions: list[AskedQuestion],
        quality_requirement: float,
        significance_level: float = 0.05,
    ) -> list[Answer]:
        # prepare state
        state_id: Final = (
            haio_hash(asked_questions[0]["question_template"])
            + ","
            + str(quality_requirement)
            + ","
            + str(significance_level)
        )
        if state_id not in self._sequential_cta_3_method_state:
            self._sequential_cta_3_method_state[state_id] = {
                "task_number": 0,
                "task_clusters_dict": {},
                "answer_candidate_lists": {},
                "task_phases": SortedDict(),
                "question_template": asked_questions[0]["question_template"],
                "data_lists": [],
            }
            for client in self.ai_clients.keys():
                self._sequential_cta_3_method_state[state_id]["answer_candidate_lists"][
                    client
                ] = []
            self._sequential_cta_3_method_state[state_id]["answer_candidate_lists"][
                "human"
            ] = []
        state: Final = self._sequential_cta_3_method_state[state_id]

        # Update state with additional questions
        # make task clusters and record answers
        for i, asked_question in enumerate(asked_questions):
            for client in self.ai_clients.keys():
                ai_answer = await self.ask_get_answer(
                    question_template=asked_question["question_template"],
                    data_list=asked_question["data_list"],
                    client=client,
                )
                state["answer_candidate_lists"][client].append(ai_answer)

                task_cluster_id = client + ai_answer
                if task_cluster_id not in state["task_clusters_dict"]:
                    state["task_clusters_dict"][task_cluster_id] = {
                        "task_indexes": set(),
                        "client": client,
                        "approved": False,
                        "correct_count": 0,
                        "incorrect_count": 0,
                    }
                state["task_clusters_dict"][task_cluster_id]["task_indexes"].add(
                    state["task_number"] + i
                )
            state["answer_candidate_lists"]["human"].append(None)
        # update task_number
        state["task_number"] += len(asked_questions)
        # update asked_questions
        state["data_lists"].extend(
            [asked_question["data_list"] for asked_question in asked_questions]
        )
        # make task phase
        state["task_phases"][
            state["task_number"]
        ] = (
            set()
        )  # task with index will be in task_phase_n if key_(n-1) <= index < key_n

        # prepare
        answer_list: Final[list[Answer | None]] = [None] * (state["task_number"])
        task_clusters_dict: Final[dict[str, HAIOClient.TaskCluster]] = copy.deepcopy(
            state["task_clusters_dict"]
        )
        task_phases: Final = copy.deepcopy(state["task_phases"])
        incomplete_task_indexes: Final[list[int]] = list(range(state["task_number"]))

        # start cta
        while incomplete_task_indexes:
            candidate_task_index = random.choice(incomplete_task_indexes)
            task_phase_index = task_phases.keys()[
                task_phases.bisect_right(candidate_task_index)
            ]
            task_phase = task_phases[task_phase_index]
            task_index: int
            human_answer: Answer
            if task_phase:
                # reuse
                if candidate_task_index in task_phase:
                    task_index = candidate_task_index
                else:
                    task_index = random.choice(list(task_phase))
                task_phases[task_phase_index].remove(task_index)
                human_answer = state["answer_candidate_lists"]["human"][task_index]
            else:
                # sample new
                task_index = candidate_task_index
                human_answer = await self.ask_get_answer(
                    question_template=state["question_template"],
                    data_list=state["data_lists"][task_index],
                    client="human",
                )
                state["answer_candidate_lists"]["human"][task_index] = human_answer
                state["data_lists"][task_index] = None
                state["task_phases"][task_phase_index].add(task_index)

            incomplete_task_indexes.remove(task_index)
            answer_list[task_index] = human_answer

            # update task clusters
            for task_cluster in task_clusters_dict.values():
                if (
                    not task_cluster["approved"]
                    and task_index in task_cluster["task_indexes"]
                ):
                    if (
                        state["answer_candidate_lists"][task_cluster["client"]][
                            task_index
                        ]
                        == human_answer
                    ):
                        task_cluster["correct_count"] += 1
                    else:
                        task_cluster["incorrect_count"] += 1

                    # check task clusters
                    binomtest_result = binomtest(
                        k=task_cluster["correct_count"],
                        n=task_cluster["correct_count"]
                        + task_cluster["incorrect_count"],
                        p=quality_requirement,
                        alternative="greater",
                    )
                    if binomtest_result.pvalue < significance_level:
                        task_cluster["approved"] = True
                        for inner_task_index in task_cluster["task_indexes"]:
                            if answer_list[inner_task_index] == None:
                                answer_list[inner_task_index] = state[
                                    "answer_candidate_lists"
                                ][task_cluster["client"]][inner_task_index]

            # check if questions have been answered
            if None not in answer_list[-len(asked_questions) :]:
                return answer_list[-len(asked_questions) :]

        return []

    async def wait(
        self,
        asked_questions: AskedQuestion | list[AskedQuestion],
        execution_config: dict,
    ) -> Answer | list[Answer]:
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

            elif execution_config["method"] == "sequential_cta_1":

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

                return await self._sequential_cta_1_method(
                    asked_questions=asked_questions,
                    quality_requirement=quality_requirement,
                    significance_level=significance_level,
                )

            elif execution_config["method"] == "sequential_cta_2":

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
                sample_size = execution_config.get("sample_size", None)
                if sample_size is None or not 0 < sample_size:
                    raise Exception("Sample size is not set.")
                question_template = asked_questions[0]["question_template"]
                if question_template["answer"]["type"] != "select":
                    raise Exception("The answer type must be select.")

                return await self._sequential_cta_2_method(
                    asked_questions=asked_questions,
                    quality_requirement=quality_requirement,
                    sample_size=sample_size,
                    significance_level=significance_level,
                )

            elif execution_config["method"] == "sequential_cta_3":

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

                return await self._sequential_cta_3_method(
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

from typing import TypedDict


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


class DataListCache(TypedDict):
    data_list: DataList
    answer_list: dict[str, dict]


class HAIOCache(TypedDict):
    question_template: QuestionTemplate
    data_lists: dict[str, DataListCache]

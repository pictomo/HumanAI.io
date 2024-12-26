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

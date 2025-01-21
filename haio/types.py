from typing import TypedDict, Literal


class ImutableAnswer(TypedDict):
    type: Literal["number", "text"]


class MutableAnswer(TypedDict):
    type: Literal["select"]
    options: list[str]


class QuestionConfig(TypedDict):
    title: str
    description: str
    question: list
    answer: ImutableAnswer | MutableAnswer


class QuestionTemplate(TypedDict):
    title: str
    description: str
    question: list
    answer: ImutableAnswer | MutableAnswer


DataList = list[str]

Answer = str

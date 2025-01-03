from typing import Any
from haio import OpenAI_IO, MTurk_IO, HAIOClient, QuestionTemplate
import asyncio
from icecream import ic


async def main() -> None:
    openai_io = OpenAI_IO()
    mturk_io = MTurk_IO()

    haio_client = HAIOClient(mturk_io=mturk_io, openai_io=openai_io)

    question_template: QuestionTemplate

    # text-insert
    data_lists = [
        ["https://s3.amazonaws.com/cv-demo-images/one-bird.jpg"],
        ["https://s3.amazonaws.com/cv-demo-images/two-birds.jpg"],
        ["https://s3.amazonaws.com/cv-demo-images/cats-and-dogs.jpg"],
        ["https://s3.amazonaws.com/cv-demo-images/basketball-outdoor.jpg"],
    ]

    question_template = {
        "title": "Classify the image.",
        "description": "Classify the image.",
        "question": [
            {
                "tag": "h2",
                "value": "Is the number of animals in the image 0, 1, or multiple?",
            },
            {
                "tag": "p",
                "value": "Please do not count humans as animals.",
            },
            {
                "tag": "img",
                "src": 0,
            },
        ],
        "answer": {"type": "select", "options": ["0", "1", "multiple"]},
    }

    asked_questions: list = []

    for data_list in data_lists:
        asked_questions.append(
            haio_client.ask(
                question_template=question_template,
                data_list=data_list,
            )
        )

    execution_config = {
        "method": "cta",
        "quality_requirement": 0.9,
    }

    answer_list = await haio_client.wait(
        asked_questions=asked_questions,
        execution_config=execution_config,
    )

    print(answer_list)


if __name__ == "__main__":
    asyncio.run(main())

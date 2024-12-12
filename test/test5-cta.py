from typing import Any
from haio import OpenAI_IO, MTurk_IO, HAIOClient, QuestionTemplate
import asyncio
from icecream import ic


async def main() -> None:
    ai_client = OpenAI_IO()
    human_client = MTurk_IO()

    haio_client = HAIOClient(humna_client=human_client, ai_client=ai_client)

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

    asked_questions = []

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

    answer_list_aiotask = asyncio.create_task(
        haio_client.wait(
            asked_questions=asked_questions,
            execution_config=execution_config,
        )
    )

    answer_list = await answer_list_aiotask

    print(answer_list)


if __name__ == "__main__":
    asyncio.run(main())

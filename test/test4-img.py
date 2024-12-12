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
    ]

    question_template = {
        "title": "Describe Image",
        "description": "Describe the image.",
        "question": [
            {
                "tag": "h2",
                "value": "Please briefly describe the image.",
            },
            {
                "tag": "img",
                "src": 0,
            },
        ],
        "answer": {"type": "text"},
    }

    print(
        await haio_client.ask_get_answer(
            question_template=question_template,
            data_list=data_lists[0],
            client="ai",
        )
    )

    # asked_questions = []

    # for data_list in data_lists:
    #     asked_questions.append(
    #         haio_client.ask(
    #             question_template=question_template,
    #             data_list=data_list,
    #         )
    #     )

    # answer_list_aiotask = asyncio.create_task(
    #     haio_client.wait(
    #         asked_questions=asked_questions,
    #     )
    # )

    # answer_list = await answer_list_aiotask

    # print(answer_list)


if __name__ == "__main__":
    asyncio.run(main())

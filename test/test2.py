from typing import Any
from haio import OpenAI_IO, MTurk_IO, HAIOClient
import asyncio


async def main() -> None:
    ai_client = OpenAI_IO()
    human_client = MTurk_IO()

    haio_client = HAIOClient(humna_client=human_client, ai_client=ai_client)

    data_list = [
        "A penny saved is a penny gained.",
        "No pain, no gain.",
    ]

    question_config: Any

    # select
    question_config = {
        "title": "Favorite Phrase or Saying",
        "description": "Please choose your favorite phrase or saying.",
        "question": [
            {
                "tag": "h2",
                "value": "Which is your favorite phrase or saying?",
            },
            {
                "tag": "p",
                "value": 0,
            },
            {
                "tag": "p",
                "value": 1,
            },
        ],
        "answer": {"type": "select", "options": ["1", "2"]},
    }

    # # select
    # question_config = {
    #     "title": "Favorite Phrase or Saying",
    #     "description": "Please choose your favorite phrase or saying.",
    #     "question": [
    #         {
    #             "tag": "h2",
    #             "value": "Which is your favorite phrase or saying?",
    #         },
    #         {
    #             "tag": "p",
    #             "value": "1. A penny saved is a penny gained.",
    #         },
    #         {
    #             "tag": "p",
    #             "value": "2. No pain, no gain.",
    #         },
    #     ],
    #     "answer": {"type": "select", "options": ["1", "2"]},
    # }

    # text-insert
    data_list = ["What is your favorite phrase or saying?"]

    question_config = {
        "title": "Favorite Phrase or Saying",
        "description": "Please tell me your favorite phrase or saying.",
        "question": [
            {
                "tag": "h2",
                "value": 0,
            },
        ],
        "answer": {"type": "text"},
    }

    # # text
    # question_config = {
    #     "title": "Favorite Phrase or Saying",
    #     "description": "Please tell me your favorite phrase or saying.",
    #     "question": [
    #         {
    #             "tag": "h2",
    #             "value": "What is your favorite phrase or saying?",
    #         },
    #     ],
    #     "answer": {"type": "text"},
    # }

    # # number
    # question_config = {
    #     "title": "Favorite Number",
    #     "description": "Please tell me your favorite number.",
    #     "question": [
    #         {
    #             "tag": "h2",
    #             "value": "Which is your favorite number?",
    #         },
    #     ],
    #     "answer": {"type": "number"},
    # }

    asked_question = haio_client.ask(
        question_config=question_config,
        data_list=data_list,
    )

    answer_aiotask = asyncio.create_task(
        haio_client.wait(
            asked_questions=asked_question,
        )
    )

    answer = await answer_aiotask

    print(answer)

    # answer: str = processing_client.make_hit(
    #     "What is your favorite phrase or saying? Please answer only those words. No semicolon, etc. is needed."
    # )
    # print(processing_client.is_finished("3H1C3QRA1IZ4U7SA822N5OWUK2WECM"))
    # print(processing_client.get_result("3H1C3QRA1IZ4U7SA822N5OWUK2WECM"))


if __name__ == "__main__":
    asyncio.run(main())

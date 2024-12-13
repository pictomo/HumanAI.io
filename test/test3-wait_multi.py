from typing import Any
from haio import OpenAI_IO, MTurk_IO, HAIOClient, QuestionTemplate
import asyncio
from icecream import ic


async def main() -> None:
    ai_client = OpenAI_IO()
    human_client = MTurk_IO()

    haio_client = HAIOClient(humna_client=human_client, ai_client=ai_client)

    question_template: QuestionTemplate

    data_list = [
        "A penny saved is a penny gained.",
        "No pain, no gain.",
    ]

    # select
    question_template = {
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
    # question_template = {
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
    data_lists = [
        ["What is your favorite phrase or saying?"],
        ["What is your favorite color?"],
        # ["What is your favorite food?"],
    ]

    question_template = {
        "title": "Your Favorite",
        "description": "Please tell me your favorite things.",
        "question": [
            {
                "tag": "h2",
                "value": 0,
            },
        ],
        "answer": {"type": "text"},
    }

    # # text
    # question_template = {
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
    # question_template = {
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

    asked_questions = []

    for i, data_list in enumerate(data_lists):
        asked_questions[i] = haio_client.ask(
            question_template=question_template,
            data_list=data_list,
        )

    answer_list = await haio_client.wait(
        asked_questions=asked_questions,
        execution_config={"client": "human"},
    )

    print(answer_list)


if __name__ == "__main__":
    asyncio.run(main())

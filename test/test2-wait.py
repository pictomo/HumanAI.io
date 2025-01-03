from haio import MTurk_IO, OpenAI_IO, Gemini_IO, HAIOClient, QuestionTemplate
import asyncio


async def main() -> None:
    mturk_io = MTurk_IO()
    openai_io = OpenAI_IO()
    gemini_io = Gemini_IO()

    haio_client = HAIOClient(
        mturk_io=mturk_io, openai_io=openai_io, gemini_io=gemini_io
    )

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
    data_list = ["What is your favorite phrase or saying?"]

    question_template = {
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

    asked_question = haio_client.ask(
        question_template=question_template,
        data_list=data_list,
    )

    answer = await haio_client.wait(
        asked_questions=asked_question,
        execution_config={"client": "human"},
    )

    print(answer)


if __name__ == "__main__":
    asyncio.run(main())

from haio import MTurk_IO, OpenAI_IO, Gemini_IO, HAIOClient, QuestionTemplate
import asyncio
from icecream import ic


async def main() -> None:
    mturk_io = MTurk_IO()
    openai_io = OpenAI_IO()
    gemini_io = Gemini_IO()

    haio_client = HAIOClient(
        mturk_io=mturk_io, openai_io=openai_io, gemini_io=gemini_io
    )

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

    # print(
    #     await haio_client.ask_get_answer(
    #         question_template=question_template,
    #         data_list=data_lists[0],
    #         client="ai",
    #     )
    # )

    asked_questions: list = []

    for data_list in data_lists:
        asked_questions.append(
            haio_client.ask(
                question_template=question_template,
                data_list=data_list,
            )
        )

    answer_list = await haio_client.wait(
        asked_questions=asked_questions,
        execution_config={"client": "gemini"},
    )

    print(answer_list)


if __name__ == "__main__":
    asyncio.run(main())

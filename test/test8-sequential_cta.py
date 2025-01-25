from haio import (
    MTurk_IO,
    Bedrock_IO,
    Gemini_IO,
    OpenAI_IO,
    HAIOClient,
    QuestionTemplate,
)
import asyncio
from icecream import ic


async def main() -> None:
    mturk_io = MTurk_IO()
    openai_io = OpenAI_IO()
    gemini_io = Gemini_IO()
    llama_io = Bedrock_IO("us.meta.llama3-2-90b-instruct-v1:0")
    claude_io = Bedrock_IO("us.anthropic.claude-3-5-sonnet-20241022-v2:0")

    haio_client = HAIOClient(
        mturk_io=mturk_io,
        openai_io=openai_io,
        gemini_io=gemini_io,
        llama_io=llama_io,
        claude_io=claude_io,
    )

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

    window_size = 2
    asked_questions_size = 0

    for data_list in data_lists:
        asked_questions.append(
            haio_client.ask(
                question_template=question_template,
                data_list=data_list,
            )
        )
        asked_questions_size += 1

        if asked_questions_size >= window_size:
            execution_config = {
                "method": "sequential_cta_1",
                "quality_requirement": 0.9,
            }
            execution_config = {
                "method": "sequential_cta_2",
                "quality_requirement": 0.9,
                "sample_size": 2,
            }
            execution_config = {
                "method": "sequential_cta_3",
                "quality_requirement": 0.9,
            }
            execution_config = {
                "method": "sequential_gta_1",
                "quality_requirement": 0.9,
            }
            execution_config = {
                "method": "sequential_gta_2",
                "quality_requirement": 0.9,
                "sample_size": 2,
            }
            execution_config = {
                "method": "sequential_gta_3",
                "quality_requirement": 0.9,
            }

            answer_list = await haio_client.wait(
                asked_questions=asked_questions,
                execution_config=execution_config,
            )

            print(answer_list)

            asked_questions = []
            asked_questions_size = 0


if __name__ == "__main__":
    asyncio.run(main())

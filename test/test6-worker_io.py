import asyncio
from haio import Gemini_IO, QuestionConfig


async def main() -> None:
    worker_io = Gemini_IO()
    question_config: QuestionConfig
    question_config = {
        "title": "Generate a sentence.",
        "description": "Generate a sentence.",
        "question": [
            {"tag": "p", "value": "Please say integer 1 or 2"},
        ],
        "answer": {"type": "text"},
    }
    question_config = {
        "title": "Generate a sentence.",
        "description": "Generate a sentence.",
        "question": [
            {"tag": "p", "value": "Which do you like more 1 or 2?"},
        ],
        "answer": {"type": "select", "options": ["1", "2"]},
    }
    question_config = {
        "title": "Generate a sentence.",
        "description": "Generate a sentence.",
        "question": [
            {
                "tag": "img",
                "src": "https://s3.amazonaws.com/cv-demo-images/one-bird.jpg",
            },
            # {
            #     "tag": "img",
            #     "src": "https://s3.amazonaws.com/cv-demo-images/two-birds.jpg",
            # },
            # {"tag": "p", "value": "Please describe 2 images."},
            {"tag": "p", "value": "Please describe the image."},
        ],
        "answer": {"type": "text"},
    }
    answer = await worker_io.ask_get_answer(question_config)
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())

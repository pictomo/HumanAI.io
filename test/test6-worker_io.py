import asyncio
from haio import Gemini_IO, Bedrock_IO, QuestionConfig


async def main() -> None:
    # worker_io = Gemini_IO()
    # worker_io = Bedrock_IO("us.meta.llama3-2-90b-instruct-v1:0")
    # worker_io = Bedrock_IO("us.anthropic.claude-3-5-sonnet-20241022-v2:0")
    worker_io = Bedrock_IO("us.amazon.nova-lite-v1:0")
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
            {
                "tag": "p",
                "value": "If you like more, Which do you like.",
            },
            # {
            #     "tag": "p",
            #     "value": "options: -39 90 100 200",
            # },
        ],
        "answer": {"type": "select", "options": ["-39", "90", "100", "200"]},
    }
    question_config = {
        "title": "Generate a sentence.",
        "description": "Generate a sentence.",
        "question": [
            {
                "tag": "img",
                "src": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAYAAABytg0kAAAAFUlEQVR4nGP4z8AAQv9ZQBQDAyMDADr9BQGou6mHAAAAAElFTkSuQmCC",
            },
            {
                "tag": "img",
                "src": "https://s3.amazonaws.com/cv-demo-images/one-bird.jpg",
            },
            {
                "tag": "img",
                "src": "https://s3.amazonaws.com/cv-demo-images/two-birds.jpg",
            },
            {"tag": "p", "value": "Please describe images."},
            # {"tag": "p", "value": "Please describe the image."},
        ],
        "answer": {"type": "text"},
    }
    answer = await worker_io.ask_get_answer(question_config)
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())

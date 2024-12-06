from typing import Any
from haio import OpenAI_IO, MTurk_IO
import asyncio


async def main() -> None:
    # processing_client = OpenAI_IO()
    processing_client = MTurk_IO()

    question_config: Any = {
        "title": "Favorite Phrase or Saying",
        "description": "Please just write your favorite phrase or saying.",
        "question": [
            {
                "tag": "h2",
                "value": "What is your favorite phrase or saying?",
            },
            {
                "tag": "p",
                "value": "Please answer only those words. No semicolon, etc. is needed.",
            },
            {
                "tag": "p",
                "value": "The answer will be used for experiment.",
            },
        ],
        "answer": {"type": "text"},
    }

    answer_aiotask = asyncio.create_task(
        processing_client.ask_get_answer(
            question_config=question_config,
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

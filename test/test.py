from haio import OpenAI_IO, MTurk_IO

if __name__ == "__main__":
    # processing_client = OpenAI_IO()
    processing_client = MTurk_IO()

    answer: str = processing_client.question("What is yout favorite phrase or saying?")
    print(answer)

    # answer: str = processing_client.make_hit("What is yout favorite phrase or saying?")
    # processing_client.is_finished("3ZICQFRS4IYFDVUGW3081WYXHQDZZY")
    # processing_client.get_result("3ZICQFRS4IYFDVUGW3081WYXHQDZZY")

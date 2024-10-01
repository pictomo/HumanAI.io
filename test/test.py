from haio import OpenAI_IO, MTurk_IO

if __name__ == "__main__":
    # processing_client = OpenAI_IO()
    processing_client = MTurk_IO()

    answer: str = processing_client.question("What is yout favorite phrase or saying?")
    print(answer)

    # answer: str = processing_client.make_hit("What is yout favorite phrase or saying?")
    # print(processing_client.is_finished("3H1C3QRA1IZ4U7SA822N5OWUK2WECM"))
    # print(processing_client.get_result("3H1C3QRA1IZ4U7SA822N5OWUK2WECM"))

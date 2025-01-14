from abc import abstractmethod, ABCMeta
from haio.types import QuestionConfig, Answer


class Worker_IO(metaclass=ABCMeta):
    @abstractmethod
    def ask(self, question_config: QuestionConfig) -> str:
        pass

    @abstractmethod
    def is_finished(self, id: str) -> bool:
        pass

    @abstractmethod
    def get_answer(self, asked: str) -> Answer:
        pass

    @abstractmethod
    async def ask_get_answer(self, question_config: QuestionConfig) -> Answer:
        pass

from abc import ABC, abstractmethod
from app.strategies.base import Signal


class Notifier(ABC):
    name: str = ""
    enabled: bool = False

    @abstractmethod
    def send(self, signal: Signal, formatted: str) -> bool:
        ...

    @abstractmethod
    def format_signal(self, signal: Signal) -> str:
        ...

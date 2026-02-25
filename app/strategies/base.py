"""策略插件基础框架"""
import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class Signal:
    """策略产出的信号"""
    strategy: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    title: str
    detail: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class Strategy(ABC):
    """策略抽象基类 — 所有策略插件继承此类"""
    name: str = ""
    description: str = ""
    schedule: str = ""
    needs_llm: bool = False
    enabled: bool = True

    def __init__(self):
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """从策略目录的 config.yaml 加载配置"""
        import yaml
        module_file = inspect.getfile(self.__class__)
        config_file = Path(module_file).parent / 'config.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}

    @abstractmethod
    def scan(self) -> list[Signal]:
        """扫描并产出信号"""
        ...

    def get_config(self) -> dict:
        return self._config

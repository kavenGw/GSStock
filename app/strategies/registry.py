"""策略自动发现与注册"""
import importlib
import logging
from pathlib import Path

from app.strategies.base import Strategy

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """策略注册中心 — 自动扫描 strategies/ 子目录"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._strategies = {}
        return cls._instance

    def discover(self):
        """扫描 app/strategies/ 下所有子包并注册"""
        strategies_dir = Path(__file__).parent
        for child in sorted(strategies_dir.iterdir()):
            if not child.is_dir() or child.name.startswith('_'):
                continue
            if not (child / '__init__.py').exists():
                continue
            try:
                module = importlib.import_module(f'app.strategies.{child.name}')
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type)
                            and issubclass(attr, Strategy)
                            and attr is not Strategy):
                        instance = attr()
                        if instance.enabled:
                            self._strategies[instance.name] = instance
                            logger.info(f'[策略注册] {instance.name}: {instance.description}')
            except Exception as e:
                logger.error(f'[策略注册] 加载 {child.name} 失败: {e}')

    @property
    def active(self) -> list[Strategy]:
        return list(self._strategies.values())

    def get(self, name: str) -> Strategy | None:
        return self._strategies.get(name)


registry = StrategyRegistry()

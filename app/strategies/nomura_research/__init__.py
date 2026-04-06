"""野村证券研报推送策略"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class NomuraResearchStrategy(Strategy):
    name = "nomura_research"
    description = "野村证券研报精选"
    schedule = "10 20 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.nomura_research_service import (
            NOMURA_RESEARCH_ENABLED,
            NomuraResearchService,
        )

        if not NOMURA_RESEARCH_ENABLED:
            return []

        try:
            results = NomuraResearchService.run_daily()
            new_count = results.get('new', 0)
            logger.info(f'[野村研报策略] 完成: {new_count} 篇新文章')
        except Exception as e:
            logger.error(f'[野村研报策略] 执行失败: {e}')

        return []

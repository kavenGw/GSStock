"""持仓股票研报推送策略"""

import logging

from app.strategies.base import Signal, Strategy

logger = logging.getLogger(__name__)


class ResearchReportStrategy(Strategy):

    name = "research_report"
    description = "持仓股票研报搜索与分析"
    schedule = "0 6 * * 1-5"
    enabled = True
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.research_report_service import (
            RESEARCH_REPORT_ENABLED,
            ResearchReportService,
        )

        if not RESEARCH_REPORT_ENABLED:
            return []

        try:
            results = ResearchReportService.run_daily_report()
            report_count = results.get('reports', 0)
            stock_count = results.get('stocks', 0)
            logger.info(f'[研报策略] 完成：{stock_count} 只股票，{report_count} 只有研报')
        except Exception as e:
            logger.error(f'[研报策略] 执行失败: {e}')

        return []

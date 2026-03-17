"""财报对比分析服务：识别财报新闻后获取两期数据并生成对比分析"""
import logging
import re
from datetime import date

from app import db
from app.models.news import NewsItem, NewsDerivation
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)

# 报告类型 → akshare 日期后缀映射
REPORT_TYPE_DATE_SUFFIX = {
    '年报': '1231',
    '半年报': '0630',
    '一季报': '0331',
    '三季报': '0930',
    '业绩预告': '1231',
    '业绩快报': '1231',
}


class EarningsCompareService:

    @staticmethod
    def process(news_item: NewsItem, stock_code: str, report_type: str):
        """处理单条财报新闻的对比分析"""
        if not stock_code or not report_type:
            logger.warning(f'[财报对比] 缺少 stock_code 或 report_type, news_id={news_item.id}')
            return

        existing = NewsDerivation.query.filter_by(news_item_id=news_item.id).first()
        if existing:
            return

        market = MarketIdentifier.identify(stock_code)
        if not market:
            logger.warning(f'[财报对比] 无法识别市场: {stock_code}')
            return

        try:
            if market == 'A':
                current_data, previous_data = EarningsCompareService._fetch_a_share(stock_code, report_type)
            else:
                current_data, previous_data = EarningsCompareService._fetch_yfinance(stock_code, report_type)

            if not current_data or not previous_data:
                logger.warning(f'[财报对比] 无法获取两期数据: {stock_code} {report_type}')
                return

            company_name = current_data.get('stock_name', stock_code)
            summary = EarningsCompareService._generate_analysis(
                company_name, stock_code, report_type, current_data, previous_data
            )

            if not summary:
                return

            derivation = NewsDerivation(
                news_item_id=news_item.id,
                search_query=f'{company_name} {report_type}对比',
                sources=[],
                summary=summary,
                importance=news_item.importance,
            )
            db.session.add(derivation)
            db.session.commit()
            logger.info(f'[财报对比] 完成 news_id={news_item.id}, {stock_code} {report_type}')

        except Exception as e:
            db.session.rollback()
            logger.error(f'[财报对比] 处理失败 news_id={news_item.id}: {e}')

    @staticmethod
    def _get_report_dates(report_type: str) -> tuple[str, str] | None:
        """根据报告类型计算当期和上期的日期字符串（YYYYMMDD格式）"""
        suffix = REPORT_TYPE_DATE_SUFFIX.get(report_type)
        if not suffix:
            return None

        current_year = date.today().year
        month_day = int(suffix[:2]) * 100 + int(suffix[2:])
        today_md = date.today().month * 100 + date.today().day

        if today_md >= month_day:
            current_date = f'{current_year}{suffix}'
            previous_date = f'{current_year - 1}{suffix}'
        else:
            current_date = f'{current_year - 1}{suffix}'
            previous_date = f'{current_year - 2}{suffix}'

        return current_date, previous_date

    @staticmethod
    def _fetch_a_share(stock_code: str, report_type: str) -> tuple[dict | None, dict | None]:
        """获取A股两期财报数据（akshare）"""
        from app.services.akshare_client import ak

        dates = EarningsCompareService._get_report_dates(report_type)
        if not dates:
            return None, None

        # akshare 用6位纯数字代码，剥离 .SS/.SH/.SZ 后缀
        pure_code = re.sub(r'\.(SS|SH|SZ)$', '', stock_code)

        current_date, previous_date = dates
        current_data = None
        previous_data = None

        import pandas as pd
        for target_date, label in [(current_date, '当期'), (previous_date, '上期')]:
            try:
                df = ak.stock_yjbb_em(date=target_date)
                if df is None or df.empty:
                    logger.warning(f'[财报对比] akshare {label}数据为空: {target_date}')
                    continue

                row = df[df['股票代码'] == pure_code]
                if row.empty:
                    row = df[df['股票代码'] == pure_code.zfill(6)]

                if row.empty:
                    logger.warning(f'[财报对比] 未找到 {stock_code} 的{label}数据: {target_date}')
                    continue

                row = row.iloc[0]
                data = {
                    'stock_code': stock_code,
                    'stock_name': str(row.get('股票简称', stock_code)),
                    'report_date': target_date,
                    'revenue': row.get('营业收入-营业收入'),
                    'revenue_yoy': row.get('营业收入-同比增长'),
                    'revenue_qoq': row.get('营业收入-季度环比增长'),
                    'net_profit': row.get('净利润-净利润'),
                    'net_profit_yoy': row.get('净利润-同比增长'),
                    'net_profit_qoq': row.get('净利润-季度环比增长'),
                    'eps': row.get('每股收益'),
                    'bvps': row.get('每股净资产'),
                    'roe': row.get('净资产收益率'),
                    'gross_margin': row.get('销售毛利率'),
                    'debt_ratio': row.get('资产负债比率'),
                    'ocf_per_share': row.get('每股经营现金流量'),
                }
                # 清理 NaN
                data = {k: None if pd.isna(v) else (v.item() if hasattr(v, 'item') else v)
                        for k, v in data.items()}

                if label == '当期':
                    current_data = data
                else:
                    previous_data = data

            except Exception as e:
                logger.error(f'[财报对比] akshare获取{label}数据失败: {e}')

        return current_data, previous_data

    @staticmethod
    def _fetch_yfinance(stock_code: str, report_type: str) -> tuple[dict | None, dict | None]:
        """获取美股/港股两期财报数据（yfinance）"""
        import yfinance as yf

        yf_code = MarketIdentifier.to_yfinance(stock_code)
        try:
            ticker = yf.Ticker(yf_code)

            is_annual = report_type in ('年报',)
            financials = ticker.financials if is_annual else ticker.quarterly_financials

            if financials is None or financials.empty:
                logger.warning(f'[财报对比] yfinance 无财报数据: {yf_code}')
                return None, None

            if len(financials.columns) < 2:
                logger.warning(f'[财报对比] yfinance 数据不足两期: {yf_code}')
                return None, None

            def extract_period(col_idx: int) -> dict:
                period = financials.iloc[:, col_idx]
                period_date = str(financials.columns[col_idx])[:10]
                data = {
                    'stock_code': stock_code,
                    'stock_name': stock_code,
                    'report_date': period_date,
                }
                for field in period.index:
                    val = period[field]
                    if val != val:  # NaN check
                        val = None
                    elif hasattr(val, 'item'):
                        val = val.item()
                    data[str(field)] = val
                return data

            current_data = extract_period(0)
            previous_data = extract_period(1)

            try:
                info = ticker.info
                name = info.get('shortName') or info.get('longName') or stock_code
                current_data['stock_name'] = name
                previous_data['stock_name'] = name
            except Exception:
                pass

            return current_data, previous_data

        except Exception as e:
            logger.error(f'[财报对比] yfinance获取失败 {yf_code}: {e}')
            return None, None

    @staticmethod
    def _generate_analysis(company_name: str, stock_code: str,
                           report_type: str,
                           current_data: dict, previous_data: dict) -> str | None:
        """LLM 生成对比分析"""
        from app.llm.router import llm_router
        from app.llm.prompts.earnings_compare import (
            EARNINGS_COMPARE_SYSTEM_PROMPT, build_earnings_compare_prompt
        )

        provider = llm_router.route('earnings_compare')
        if not provider:
            return None

        try:
            user_prompt = build_earnings_compare_prompt(
                company_name, stock_code, report_type, current_data, previous_data
            )
            response = provider.chat([
                {'role': 'system', 'content': EARNINGS_COMPARE_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ], temperature=0.3, max_tokens=800)
            return response.strip()
        except Exception as e:
            logger.error(f'[财报对比] LLM分析失败: {e}')
            return None

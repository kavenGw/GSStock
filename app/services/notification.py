"""
消息推送服务 - Slack Webhook
"""
import json
import logging
import ssl
import threading
from datetime import date, datetime, timedelta
from urllib.request import urlopen, Request

import certifi

from app.config.notification_config import SLACK_WEBHOOK_URL, SLACK_ENABLED

logger = logging.getLogger(__name__)


class NotificationService:
    """消息推送服务"""

    _daily_push_lock = threading.Lock()

    @staticmethod
    def get_status() -> dict:
        return {
            'slack': SLACK_ENABLED,
        }

    @staticmethod
    def send_slack(message: str) -> bool:
        if not SLACK_ENABLED:
            logger.warning('[通知.Slack] Slack 未配置')
            return False

        try:
            payload = json.dumps({'text': message}).encode('utf-8')
            req = Request(SLACK_WEBHOOK_URL, data=payload, headers={'Content-Type': 'application/json'})
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=10, context=ctx) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f'[通知.Slack] 推送失败: {e}', exc_info=True)
            return False

    @staticmethod
    def send_all(subject: str, text_content: str) -> dict:
        results = {}
        if SLACK_ENABLED:
            results['slack'] = NotificationService.send_slack(text_content)
        return results

    @staticmethod
    def _get_all_watched_codes() -> tuple[list[str], dict[str, str]]:
        """收集所有关注的股票代码（持仓+分类），返回 (codes, name_map)"""
        from app.services.position import PositionService
        from app.models.stock import Stock
        from app.models.category import StockCategory

        name_map = {}
        code_set = set()

        latest_date = PositionService.get_latest_date()
        if latest_date:
            positions = PositionService.get_snapshot(latest_date)
            for p in positions:
                code_set.add(p.stock_code)
                name_map[p.stock_code] = p.stock_name

        all_sc = StockCategory.query.all()
        sc_codes = [sc.stock_code for sc in all_sc if sc.stock_code not in code_set]
        if sc_codes:
            stocks = Stock.query.filter(Stock.stock_code.in_(sc_codes)).all()
            for s in stocks:
                code_set.add(s.stock_code)
                name_map[s.stock_code] = s.stock_name

        codes = list(code_set)
        return codes, name_map

    @staticmethod
    def format_briefing_summary() -> dict:
        """生成每日简报摘要（持仓/收益/异常）"""
        from app.services.position import PositionService

        today = date.today()
        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return {'text': '暂无持仓数据'}

        positions = PositionService.get_snapshot(latest_date)
        if not positions:
            return {'text': '暂无持仓数据'}

        total_market_value = 0
        total_cost = 0
        up_count = 0
        down_count = 0
        items = []

        for p in positions:
            mv = p.current_price * p.quantity
            cost = p.total_amount
            profit = mv - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0

            total_market_value += mv
            total_cost += cost
            if profit > 0:
                up_count += 1
            elif profit < 0:
                down_count += 1

            items.append({
                'code': p.stock_code,
                'name': p.stock_name,
                'price': p.current_price,
                'profit': profit,
                'profit_pct': profit_pct,
            })

        total_profit = total_market_value - total_cost
        total_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

        sign = '+' if total_profit >= 0 else ''

        text = f"持仓概览 ({latest_date})\n"
        text += f"总市值: ¥{total_market_value:,.0f} | 浮盈: {sign}¥{total_profit:,.0f} ({sign}{total_pct:.1f}%)\n"
        text += f"持仓: {len(positions)}只 | 盈利: {up_count} | 亏损: {down_count}\n"

        sorted_items = sorted(items, key=lambda x: x['profit_pct'], reverse=True)
        gainers = [i for i in sorted_items if i['profit_pct'] > 0]
        losers = [i for i in sorted_items if i['profit_pct'] < 0]

        if gainers:
            text += "\n盈利 Top3:\n"
            for item in gainers[:3]:
                text += f"  {item['name']}({item['code']}): +{item['profit_pct']:.1f}%\n"

        if losers:
            text += "\n亏损 Top3:\n"
            for item in losers[:3]:
                text += f"  {item['name']}({item['code']}): {item['profit_pct']:.1f}%\n"

        return {'text': text}

    @staticmethod
    def format_alert_signals(codes: list[str] = None, name_map: dict[str, str] = None) -> dict:
        """生成预警信号摘要（所有关注股票）"""
        from app.services.signal_cache import SignalCacheService
        from app.utils.market_identifier import MarketIdentifier

        if codes is None or name_map is None:
            codes, name_map = NotificationService._get_all_watched_codes()
        a_share_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]

        if not a_share_codes:
            return {'text': ''}

        signals = SignalCacheService.get_cached_signals_with_names(a_share_codes, name_map)

        buy_signals = signals.get('buy_signals', [])
        sell_signals = signals.get('sell_signals', [])

        if not buy_signals and not sell_signals:
            return {'text': ''}

        # 按 (stock_code, signal_name) 去重，保留最近一条
        def dedup(sigs):
            seen = {}
            for sig in sigs:
                key = (sig.get('stock_code', ''), sig.get('name', ''))
                if key not in seen or (sig.get('date', '') > seen[key].get('date', '')):
                    seen[key] = sig
            return list(seen.values())

        sell_signals = dedup(sell_signals)
        buy_signals = dedup(buy_signals)

        # 对立信号冲突消解：同一只股票的对立信号只保留日期最新的
        conflict_pairs = [('突破5日均线', '跌破5日均线')]
        for name_a, name_b in conflict_pairs:
            pair = {name_a, name_b}
            latest = {}  # stock_code -> (date, 'buy'|'sell')
            for sig in buy_signals:
                if sig.get('name') in pair:
                    code = sig.get('stock_code', '')
                    d = sig.get('date', '')
                    if code not in latest or d > latest[code][0]:
                        latest[code] = (d, 'buy')
            for sig in sell_signals:
                if sig.get('name') in pair:
                    code = sig.get('stock_code', '')
                    d = sig.get('date', '')
                    if code not in latest or d > latest[code][0]:
                        latest[code] = (d, 'sell')
            buy_signals = [
                s for s in buy_signals
                if s.get('name') not in pair
                or latest.get(s.get('stock_code', ''), (None, 'buy'))[1] == 'buy'
            ]
            sell_signals = [
                s for s in sell_signals
                if s.get('name') not in pair
                or latest.get(s.get('stock_code', ''), (None, 'sell'))[1] == 'sell'
            ]

        text = "预警信号\n"

        if sell_signals:
            text += "\n卖出信号:\n"
            for sig in sell_signals[:10]:
                text += f"  {sig.get('stock_name', '')}({sig.get('stock_code', '')}) - {sig.get('name', '')}\n"

        if buy_signals:
            text += "\n买入信号:\n"
            for sig in buy_signals[:10]:
                text += f"  {sig.get('stock_name', '')}({sig.get('stock_code', '')}) - {sig.get('name', '')}\n"

        return {'text': text}

    @staticmethod
    def format_earnings_alerts(codes: list[str] = None, name_map: dict[str, str] = None) -> dict:
        """生成财报日期提醒（未来7天）"""
        from app.services.earnings import EarningsService
        from app.utils.market_identifier import MarketIdentifier

        if codes is None or name_map is None:
            codes, name_map = NotificationService._get_all_watched_codes()
        non_a_codes = [c for c in codes if not MarketIdentifier.is_a_share(c)]

        if not non_a_codes:
            return {'text': ''}

        upcoming = EarningsService.get_upcoming_earnings(non_a_codes, days=7)
        if not upcoming:
            return {'text': ''}

        text = "财报提醒（未来7天）\n"
        for item in upcoming:
            name = name_map.get(item['code'], item['code'])
            if item['is_today']:
                text += f"  {name}({item['code']}) - 今天发布财报\n"
            else:
                text += f"  {name}({item['code']}) - {item['days_until']}天后({item['earnings_date']})\n"

        return {'text': text}

    @staticmethod
    def format_pe_alerts(codes: list[str] = None, name_map: dict[str, str] = None) -> dict:
        """生成PE估值预警（偏高/偏低）"""
        from app.services.earnings import EarningsService
        from app.utils.market_identifier import MarketIdentifier

        if codes is None or name_map is None:
            codes, name_map = NotificationService._get_all_watched_codes()
        non_a_codes = [c for c in codes if not MarketIdentifier.is_a_share(c)]

        if not non_a_codes:
            return {'text': ''}

        pe_data = EarningsService.get_pe_ratios(non_a_codes)

        alerts = []
        for code, data in pe_data.items():
            status = data.get('pe_status', 'na')
            if status in ('high', 'very_high', 'low'):
                name = name_map.get(code, code)
                pe_display = data.get('pe_display', '?')
                label = {'high': '偏高', 'very_high': '极高', 'low': '偏低'}[status]
                alerts.append(f"  {name}({code}) PE={pe_display} {label}")

        if not alerts:
            return {'text': ''}

        text = "PE估值预警\n" + "\n".join(alerts) + "\n"
        return {'text': text}

    @staticmethod
    def format_ai_report(analyses: list) -> dict:
        if not analyses:
            return {'text': ''}

        text = "AI分析摘要\n"

        for a in analyses:
            code = a.get('stock_code', '')
            name = a.get('stock_name', '')
            result = a.get('result', {})
            signal = result.get('signal', 'HOLD')
            score = result.get('score', '-')
            conclusion = result.get('conclusion', '')

            line = f"{name}({code}): {signal}({score}分) - {conclusion}"
            text += f"  {line}\n"

        return {'text': text}

    @staticmethod
    def push_realtime_analysis(analyses: dict) -> bool:
        """推送盯盘实时分析结果到 Slack"""
        if not analyses:
            return False

        from app.services.watch_service import WatchService
        watch_list = WatchService.get_watch_list()
        name_map = {w['stock_code']: w['stock_name'] for w in watch_list}

        signal_icons = {'buy': '🟢买入', 'sell': '🔴卖出', 'hold': '🟡持有', 'watch': '⚪观望'}
        now_str = datetime.now().strftime('%H:%M')
        lines = []

        from app.services.unified_stock_data import unified_stock_data_service
        all_codes = [c for c, p in analyses.items() if p.get('realtime')]
        raw_prices = unified_stock_data_service.get_realtime_prices(all_codes) if all_codes else {}

        for code, periods in analyses.items():
            data = periods.get('realtime')
            if not data:
                continue
            name = name_map.get(code, code)
            signal = signal_icons.get(data.get('signal', ''), '⚪观望')
            summary = data.get('summary', '')

            price_data = raw_prices.get(code, {})
            current_price = price_data.get('current_price')
            change_pct = price_data.get('change_percent')
            price_str = ''
            if current_price is not None:
                arrow = '📈' if (change_pct or 0) >= 0 else '📉'
                pct_str = f"{change_pct:+.2f}%" if change_pct is not None else ''
                price_str = f" {arrow}{current_price} ({pct_str})"

            support = data.get('support_levels', [])
            resistance = data.get('resistance_levels', [])
            sup_str = ' / '.join(str(s) for s in support) if support else '-'
            res_str = ' / '.join(str(r) for r in resistance) if resistance else '-'

            lines.append(f"{name}({code}):{price_str} {signal} {summary}")
            lines.append(f"  支撑: {sup_str} | 压力: {res_str}")

        if not lines:
            return False

        message = f"📊 盯盘实时分析 ({now_str})\n" + "\n".join(lines)
        return NotificationService.send_slack(message)

    @staticmethod
    def format_watch_analysis(analyses: dict) -> dict:
        """格式化盯盘AI分析结果用于推送"""
        if not analyses:
            return {'text': ''}

        from app.services.watch_service import WatchService
        watch_list = WatchService.get_watch_list()
        name_map = {w['stock_code']: w['stock_name'] for w in watch_list}

        signal_map = {'buy': '买入', 'sell': '卖出', 'hold': '持有', 'watch': '观望'}
        lines = []

        for code, periods in analyses.items():
            name = name_map.get(code, code)
            parts = []
            for period in ('7d', '30d'):
                data = periods.get(period)
                if not data:
                    continue
                signal = signal_map.get(data.get('signal', ''), '观望')
                summary = data.get('summary', '')
                parts.append(f"[{period}]{signal} {summary}")
            if parts:
                lines.append(f"  {name}({code}): {' | '.join(parts)}")

        if not lines:
            return {'text': ''}

        text = "盯盘分析\n" + "\n".join(lines) + "\n"
        return {'text': text}

    @staticmethod
    def format_indices_summary() -> str:
        """格式化指数行情用于推送"""
        try:
            from app.services.briefing import BriefingService
            data = BriefingService.get_indices_data()
            regions = data.get('regions', [])
            indices = data.get('indices', {})
            if not regions:
                return ''

            lines = ['指数行情']
            for region in regions:
                key = region['key']
                region_indices = indices.get(key, [])
                region_lines = []
                for idx in region_indices:
                    if idx.get('close') is None:
                        continue
                    pct = idx.get('change_percent')
                    pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                    region_lines.append(f"  {idx['name']}: {idx['close']:,.2f} ({pct_str})")
                if region_lines:
                    lines.append(f"\n  [{region['name']}]")
                    lines.extend(region_lines)

            return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.指数] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_futures_summary() -> str:
        """格式化期货数据用于推送"""
        try:
            from app.services.briefing import BriefingService
            data = BriefingService.get_futures_data()
            futures = data.get('futures', [])
            if not futures:
                return ''

            lines = ['期货数据']
            for f in futures:
                if f.get('close') is None:
                    continue
                pct = f.get('change_percent')
                pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                lines.append(f"  {f['name']}: {f['close']:,.2f} ({pct_str})")

            return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.期货] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_etf_premium_summary() -> str:
        """格式化ETF溢价率用于推送"""
        try:
            from app.services.briefing import BriefingService
            data = BriefingService.get_etf_premium_data()
            etfs = data.get('etfs', [])
            if not etfs:
                return ''

            signal_map = {'buy': '适合买入', 'sell': '溢价过高', 'normal': '正常'}
            lines = ['ETF溢价']
            for etf in etfs:
                if etf.get('premium_rate') is None:
                    continue
                signal = signal_map.get(etf.get('signal', ''), '')
                signal_str = f" {signal}" if signal else ''
                lines.append(f"  {etf['name']}({etf['code']}): 溢价 {etf['premium_rate']:+.2f}%{signal_str}")

            return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.ETF溢价] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_sectors_summary() -> str:
        """格式化板块涨跌用于推送"""
        try:
            from app.services.briefing import BriefingService

            lines = ['板块涨跌']

            cn_sectors = BriefingService.get_cn_sectors_data()
            if cn_sectors:
                lines.append('\n  [A股行业Top5]')
                for s in cn_sectors:
                    leader = f" 领涨: {s['leader']}" if s.get('leader') else ''
                    lines.append(f"  {s['name']}: {s['change_percent']:+.2f}%{leader}")

            us_sectors = BriefingService.get_us_sectors_data()
            if us_sectors:
                lines.append('\n  [美股行业Top5]')
                for s in us_sectors:
                    lines.append(f"  {s['name']}: {s['change_percent']:+.2f}%")

            return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.板块] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_dram_summary() -> str:
        """格式化DRAM价格用于推送"""
        try:
            from app.services.dram_price import DramPriceService
            data = DramPriceService.get_dram_data()
            today_data = data.get('today', [])
            if not today_data:
                return ''

            lines = ['DRAM价格']
            for item in today_data:
                if item.get('avg_price') is None:
                    continue
                pct = item.get('change_pct')
                pct_str = f" ({pct:+.2f}%)" if pct is not None else ''
                lines.append(f"  {item['label']}: ${item['avg_price']:.2f}{pct_str}")

            return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.DRAM] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_technical_summary() -> str:
        """格式化技术评分用于推送"""
        try:
            from app.services.briefing import BriefingService, BRIEFING_STOCKS
            data = BriefingService.get_stocks_technical_data()
            if not data:
                return ''

            name_map = {s['code']: s['name'] for s in BRIEFING_STOCKS}
            lines = ['技术评分']
            for code, info in data.items():
                name = name_map.get(code, code)
                score = info.get('score', 0)
                signal_text = info.get('signal_text', '')
                macd = info.get('macd_signal', '')
                lines.append(f"  {name}({code}): {score}分 {signal_text} MACD:{macd}")

            return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.技术评分] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_github_release_updates() -> tuple[list[str], list[tuple[str, str]]]:
        """格式化所有 GitHub 仓库的版本更新摘要

        Returns:
            (texts, pushed_versions)
            - texts: 每个有更新的仓库一段文本
            - pushed_versions: [(key, version), ...] 需要标记已推送的版本
        """
        texts = []
        pushed_versions = []
        try:
            from app.services.github_release import GitHubReleaseService
            all_updates = GitHubReleaseService.get_all_updates()

            for item in all_updates:
                cfg = item['config']
                releases = item['releases']
                if not releases:
                    continue

                latest_version = releases[0]['version']
                pushed_versions.append((cfg['key'], latest_version))

                # GLM 摘要
                try:
                    from app.llm.router import llm_router
                    from app.llm.prompts.github_release_update import (
                        GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT, build_github_release_update_prompt,
                    )

                    provider = llm_router.route('github_release_update')
                    if provider:
                        prompt = build_github_release_update_prompt(cfg['name'], releases)
                        summary = provider.chat(
                            [
                                {'role': 'system', 'content': GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT},
                                {'role': 'user', 'content': prompt},
                            ],
                            temperature=0.3,
                            max_tokens=500,
                        )
                        texts.append(f"{cfg['emoji']} {cfg['name']} 更新\n{summary.strip()}")
                        continue
                except Exception as e:
                    logger.warning(f"[通知.{cfg['name']}更新] GLM摘要失败: {e}")

                # 降级：纯文本
                lines = [f"{cfg['emoji']} {cfg['name']} 更新"]
                for r in releases:
                    lines.append(f"{r['version']} ({r['published_at']})")
                texts.append('\n'.join(lines))
        except Exception as e:
            logger.warning(f'[通知.GitHub Release更新] 获取失败: {e}')

        return texts, pushed_versions

    @staticmethod
    def push_daily_report(include_ai: bool = False) -> dict:
        """一键推送每日报告（持仓+简报数据+GLM总结+预警+盯盘分析）"""
        with NotificationService._daily_push_lock:
            today = date.today()

            if NotificationService.has_daily_push(today):
                logger.info('[通知] 今日已推送，跳过')
                return {'skipped': True}

            NotificationService._mark_daily_push(today)

        subject = f'每日股票分析报告 - {today}'

        codes, name_map = NotificationService._get_all_watched_codes()

        # 收集所有结构化数据
        briefing = NotificationService.format_briefing_summary()
        alerts = NotificationService.format_alert_signals(codes, name_map)
        earnings = NotificationService.format_earnings_alerts(codes, name_map)
        pe = NotificationService.format_pe_alerts(codes, name_map)

        indices_text = NotificationService.format_indices_summary()
        futures_text = NotificationService.format_futures_summary()
        etf_text = NotificationService.format_etf_premium_summary()
        sectors_text = NotificationService.format_sectors_summary()
        dram_text = NotificationService.format_dram_summary()
        technical_text = NotificationService.format_technical_summary()

        ai_text = ''
        if include_ai:
            try:
                from app.services.ai_analyzer import AIAnalyzerService, AI_ENABLED
                if AI_ENABLED:
                    ai_service = AIAnalyzerService()
                    from app.services.position import PositionService
                    latest_date = PositionService.get_latest_date()
                    if latest_date:
                        positions = PositionService.get_snapshot(latest_date)
                        stock_list = [{'code': p.stock_code, 'name': p.stock_name} for p in positions]
                        analyses = ai_service.analyze_batch(stock_list)
                        ai_report = NotificationService.format_ai_report(analyses)
                        ai_text = ai_report.get('text', '')
            except Exception as e:
                logger.warning(f'[通知.AI报告] 生成失败: {e}')

        # 盯盘分析（7d + 30d）
        watch_text = ''
        try:
            from app.services.watch_analysis_service import WatchAnalysisService
            WatchAnalysisService.analyze_stocks('7d')
            WatchAnalysisService.analyze_stocks('30d')
            from app.services.watch_service import WatchService
            watch_analyses = WatchService.get_all_today_analyses()
            watch_report = NotificationService.format_watch_analysis(watch_analyses)
            watch_text = watch_report.get('text', '')
        except Exception as e:
            logger.warning(f'[通知.盯盘分析] 生成失败: {e}')

        # GitHub Release 版本更新
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()

        # GLM 综合分析
        core_insights = ''
        action_suggestions = ''
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.daily_briefing import (
                DAILY_BRIEFING_SYSTEM_PROMPT, build_daily_briefing_prompt,
            )

            provider = llm_router.route('daily_briefing')
            if provider:
                all_data = {
                    'position_summary': briefing.get('text', ''),
                    'indices': indices_text,
                    'futures': futures_text,
                    'etf_premium': etf_text,
                    'sectors': sectors_text,
                    'dram': dram_text,
                    'technical': technical_text,
                    'alert_signals': alerts.get('text', ''),
                    'earnings_alerts': earnings.get('text', ''),
                    'pe_alerts': pe.get('text', ''),
                    'watch_analysis': watch_text,
                }
                prompt = build_daily_briefing_prompt(all_data)
                response = provider.chat(
                    [
                        {'role': 'system', 'content': DAILY_BRIEFING_SYSTEM_PROMPT},
                        {'role': 'user', 'content': prompt},
                    ],
                    temperature=0.3,
                    max_tokens=1000,
                )
                cleaned = response.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                parsed = json.loads(cleaned)
                core_insights = parsed.get('core_insights', '')
                action_suggestions = parsed.get('action_suggestions', '')
        except Exception as e:
            logger.warning(f'[通知.GLM总结] 生成失败: {e}')

        # 组装最终消息
        text_parts = []

        if core_insights:
            text_parts.append(f"🎯 今日核心观点\n{core_insights}")

        text_parts.append(briefing['text'])

        if indices_text:
            text_parts.append(indices_text)
        if futures_text:
            text_parts.append(futures_text)
        if etf_text:
            text_parts.append(etf_text)
        if sectors_text:
            text_parts.append(sectors_text)
        if dram_text:
            text_parts.append(dram_text)
        if technical_text:
            text_parts.append(technical_text)
        if alerts.get('text'):
            text_parts.append(alerts['text'])
        if earnings.get('text'):
            text_parts.append(earnings['text'])
        if pe.get('text'):
            text_parts.append(pe['text'])
        if ai_text:
            text_parts.append(ai_text)
        if watch_text:
            text_parts.append(watch_text)

        for rt in release_texts:
            text_parts.append(rt)

        if action_suggestions:
            text_parts.append(f"💡 操作建议\n{action_suggestions}")

        full_text = '\n---\n'.join(text_parts)

        # 标记已推送的 GitHub Release 版本
        if release_pushed_versions:
            from app.services.github_release import GitHubReleaseService
            for key, version in release_pushed_versions:
                GitHubReleaseService.mark_pushed_version(key, version)

        results = NotificationService.send_all(subject, full_text)
        results['content_preview'] = full_text[:500]
        return results

    @staticmethod
    def _mark_daily_push(push_date: date) -> None:
        import os
        try:
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
            os.makedirs(data_dir, exist_ok=True)
            flag_path = os.path.join(data_dir, f'daily_push_{push_date.isoformat()}.flag')
            with open(flag_path, 'w') as f:
                f.write('')
            NotificationService.cleanup_old_flags()
        except OSError as e:
            logger.warning(f'[通知] 写入推送标记失败: {e}')

    @staticmethod
    def has_daily_push(push_date: date) -> bool:
        import os
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        flag_path = os.path.join(data_dir, f'daily_push_{push_date.isoformat()}.flag')
        return os.path.exists(flag_path)

    @staticmethod
    def cleanup_old_flags(keep_days: int = 7) -> None:
        import os
        import glob as glob_mod
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        cutoff = date.today() - timedelta(days=keep_days)
        pattern = os.path.join(data_dir, 'daily_push_*.flag')
        for f in glob_mod.glob(pattern):
            basename = os.path.basename(f)
            try:
                date_str = basename.replace('daily_push_', '').replace('.flag', '')
                flag_date = date.fromisoformat(date_str)
                if flag_date < cutoff:
                    os.remove(f)
            except (ValueError, OSError):
                pass

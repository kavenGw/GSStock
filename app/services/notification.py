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

        for code, periods in analyses.items():
            data = periods.get('realtime')
            if not data:
                continue
            name = name_map.get(code, code)
            signal = signal_icons.get(data.get('signal', ''), '⚪观望')
            summary = data.get('summary', '')

            support = data.get('support_levels', [])
            resistance = data.get('resistance_levels', [])
            sup_str = ' / '.join(str(s) for s in support) if support else '-'
            res_str = ' / '.join(str(r) for r in resistance) if resistance else '-'

            lines.append(f"{name}({code}): {signal} {summary}")
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
    def push_daily_report(include_ai: bool = False) -> dict:
        """一键推送每日报告（简报+预警信号+财报提醒+PE预警+AI分析）"""
        with NotificationService._daily_push_lock:
            today = date.today()

            if NotificationService.has_daily_push(today):
                logger.info('[通知] 今日已推送，跳过')
                return {'skipped': True}

            # 先标记，防止并发重复推送
            NotificationService._mark_daily_push(today)

        subject = f'每日股票分析报告 - {today}'

        codes, name_map = NotificationService._get_all_watched_codes()

        briefing = NotificationService.format_briefing_summary()
        alerts = NotificationService.format_alert_signals(codes, name_map)
        earnings = NotificationService.format_earnings_alerts(codes, name_map)
        pe = NotificationService.format_pe_alerts(codes, name_map)

        text_parts = [briefing['text']]

        if alerts.get('text'):
            text_parts.append(alerts['text'])
        if earnings.get('text'):
            text_parts.append(earnings['text'])
        if pe.get('text'):
            text_parts.append(pe['text'])

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
                        if ai_report['text']:
                            text_parts.append(ai_report['text'])
            except Exception as e:
                logger.warning(f'[通知.AI报告] 生成失败: {e}')

        # 盯盘分析（7d + 30d）
        try:
            from app.services.watch_analysis_service import WatchAnalysisService
            WatchAnalysisService.analyze_stocks('7d')
            WatchAnalysisService.analyze_stocks('30d')
            from app.services.watch_service import WatchService
            watch_analyses = WatchService.get_all_today_analyses()
            watch_report = NotificationService.format_watch_analysis(watch_analyses)
            if watch_report['text']:
                text_parts.append(watch_report['text'])
        except Exception as e:
            logger.warning(f'[通知.盯盘分析] 生成失败: {e}')

        full_text = '\n---\n'.join(text_parts)

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

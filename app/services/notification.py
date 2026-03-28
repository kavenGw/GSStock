"""
消息推送服务 - Slack Bot Token (chat.postMessage)
"""
import json
import logging
import ssl
import threading
from datetime import date, datetime, timedelta
from urllib.request import urlopen, Request

import certifi

from app.config.notification_config import (
    SLACK_BOT_TOKEN, SLACK_ENABLED,
    CHANNEL_NEWS, CHANNEL_WATCH, CHANNEL_AI_TOOL, CHANNEL_LOL, CHANNEL_NBA, CHANNEL_DAILY,
    CHANNEL_OPERATION,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """消息推送服务"""

    _daily_push_lock = threading.Lock()

    @staticmethod
    def get_status() -> dict:
        return {
            'slack': SLACK_ENABLED,
        }

    _signal_state = {}  # 类变量，状态机去重

    @staticmethod
    def _make_signal_key(signal) -> str:
        data = signal.data or {}
        stock_code = data.get('stock_code') or data.get('code', '')
        signal_name = data.get('name', '')
        if stock_code and signal_name:
            return f"{signal.strategy}:{stock_code}:{signal_name}"
        return ''

    @staticmethod
    def _get_signal_direction(signal) -> str:
        data = signal.data or {}
        direction = data.get('type', '')
        if direction:
            return direction
        change_pct = data.get('change_pct')
        if change_pct is not None:
            return 'up' if change_pct > 0 else 'down'
        return ''

    @staticmethod
    def _is_duplicate(signal) -> bool:
        key = NotificationService._make_signal_key(signal)
        if not key:
            return False
        direction = NotificationService._get_signal_direction(signal)
        if not direction:
            return False
        last_direction = NotificationService._signal_state.get(key)
        if last_direction == direction:
            logger.debug(f'[通知去重] 跳过重复信号: {key} direction={direction}')
            return True
        NotificationService._signal_state[key] = direction
        return False

    @staticmethod
    def dispatch_signal(signal):
        """事件总线回调：去重 + 格式化 + 按策略路由频道"""
        if signal.priority == "LOW":
            return
        if NotificationService._is_duplicate(signal):
            return
        emoji = {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1"}.get(signal.priority, "")
        text = f"{emoji} *[{signal.strategy}]* {signal.title}\n{signal.detail}"
        channel = CHANNEL_WATCH if signal.strategy == 'watch_alert' else CHANNEL_NEWS
        NotificationService.send_slack(text, channel)

    @staticmethod
    def send_slack(message: str, channel: str = CHANNEL_NEWS) -> bool:
        if not SLACK_ENABLED:
            logger.warning('[通知.Slack] Slack 未配置')
            return False

        try:
            payload = json.dumps({'channel': channel, 'text': message}).encode('utf-8')
            req = Request(
                'https://slack.com/api/chat.postMessage',
                data=payload,
                headers={
                    'Content-Type': 'application/json; charset=utf-8',
                    'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
                },
            )
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=10, context=ctx) as resp:
                body = json.loads(resp.read().decode('utf-8'))
                if not body.get('ok'):
                    logger.error(f'[通知.Slack] API 错误: {body.get("error", "unknown")}')
                    return False
                return True
        except Exception as e:
            logger.error(f'[通知.Slack] 推送失败: {e}', exc_info=True)
            return False

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

        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return {'text': '暂无持仓数据'}

        positions = PositionService.get_snapshot(latest_date)
        if not positions:
            return {'text': '暂无持仓数据'}

        total_market_value = 0
        total_cost = 0
        items = []

        for p in positions:
            mv = p.current_price * p.quantity
            cost = p.total_amount
            profit = mv - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0

            total_market_value += mv
            total_cost += cost

            items.append({
                'code': p.stock_code,
                'name': p.stock_name,
                'price': p.current_price,
                'profit': profit,
                'profit_pct': profit_pct,
            })

        total_profit = total_market_value - total_cost
        total_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

        text = f"📊 持仓 ({latest_date}) | ¥{total_market_value:,.0f} | {total_pct:+.1f}%\n"

        sorted_items = sorted(items, key=lambda x: x['profit_pct'], reverse=True)
        gainers = [i for i in sorted_items if i['profit_pct'] >= 0]
        losers = [i for i in sorted_items if i['profit_pct'] < 0]

        if gainers:
            parts = [f"🟢{i['name']} {i['profit_pct']:+.1f}%" for i in gainers]
            text += ' | '.join(parts) + '\n'
        if losers:
            parts = [f"🔴{i['name']} {i['profit_pct']:+.1f}%" for i in losers]
            text += ' | '.join(parts)

        return {'text': text.rstrip('\n')}

    @staticmethod
    def format_alert_signals(codes: list[str] = None, name_map: dict[str, str] = None,
                             position_codes: set[str] = None) -> dict:
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

        grouped = {}
        for sig in buy_signals:
            code = sig.get('stock_code', '')
            if code not in grouped:
                grouped[code] = {'name': sig.get('stock_name', code), 'buy': [], 'sell': []}
            grouped[code]['buy'].append(sig.get('name', ''))
        for sig in sell_signals:
            code = sig.get('stock_code', '')
            if code not in grouped:
                grouped[code] = {'name': sig.get('stock_name', code), 'buy': [], 'sell': []}
            grouped[code]['sell'].append(sig.get('name', ''))

        text = "⚡ 关键信号\n"

        if position_codes:
            pos_codes = [c for c in grouped if c in position_codes]
            watch_codes = [c for c in grouped if c not in position_codes]
        else:
            pos_codes = []
            watch_codes = list(grouped.keys())

        if pos_codes:
            text += "\n持仓:\n"
            for code in pos_codes:
                g = grouped[code]
                parts = []
                for s in g['sell']:
                    parts.append(f"🔴{s}")
                for s in g['buy']:
                    parts.append(f"🟢{s}")
                text += f"  {g['name']} {' '.join(parts)}\n"

        if watch_codes:
            # 同时有买卖信号的关注股票：保留最新方向
            for code in watch_codes:
                g = grouped[code]
                if g['buy'] and g['sell']:
                    buy_latest = max(
                        (s.get('date', '') for s in buy_signals
                         if s.get('stock_code') == code), default='')
                    sell_latest = max(
                        (s.get('date', '') for s in sell_signals
                         if s.get('stock_code') == code), default='')
                    if buy_latest >= sell_latest:
                        g['sell'] = []
                    else:
                        g['buy'] = []

            text += "\n关注:\n"
            sell_parts = []
            buy_parts = []
            for code in watch_codes:
                g = grouped[code]
                for s in g['sell']:
                    sell_parts.append(f"{g['name']}·{s}")
                for s in g['buy']:
                    buy_parts.append(f"{g['name']}·{s}")
            if sell_parts:
                text += f"  🔴卖出: {' | '.join(sell_parts[:8])}\n"
            if buy_parts:
                text += f"  🟢买入: {' | '.join(buy_parts[:8])}\n"

        return {'text': text.rstrip('\n')}

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

        text = "📅 财报提醒（未来7天）\n"
        for item in upcoming:
            name = name_map.get(item['code'], item['code'])
            if item['is_today']:
                text += f"  {name}({item['code']}) - 今天发布财报\n"
            else:
                text += f"  {name}({item['code']}) - {item['days_until']}天后({item['earnings_date']})\n"

        return {'text': text.rstrip('\n')}

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
                alerts.append(f"{name} PE={pe_display} {label}")

        if not alerts:
            return {'text': ''}

        if len(alerts) == 1:
            text = f"⚠️ PE预警: {alerts[0]}"
        else:
            text = "⚠️ PE预警\n" + "\n".join(f"  {a}" for a in alerts)
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
        return NotificationService.send_slack(message, CHANNEL_WATCH)

    @staticmethod
    def format_watch_analysis(analyses: dict) -> dict:
        """格式化盯盘AI分析结果用于推送"""
        if not analyses:
            return {'text': ''}

        from app.services.watch_service import WatchService
        watch_list = WatchService.get_watch_list()
        name_map = {w['stock_code']: w['stock_name'] for w in watch_list}

        signal_emoji = {'buy': '🟢', 'sell': '🔴', 'hold': '🟡'}
        signal_map = {'buy': '买入', 'sell': '卖出', 'hold': '持有', 'watch': '观望'}
        lines = []

        for code, periods in analyses.items():
            name = name_map.get(code, code)
            parts = []
            for period in ('7d', '30d'):
                data = periods.get(period)
                if not data:
                    continue
                sig_key = data.get('signal', '')
                signal = signal_map.get(sig_key, '观望')
                emoji = signal_emoji.get(sig_key, '')
                summary = data.get('summary', '')
                if len(summary) > 30:
                    summary = summary[:30] + '…'
                parts.append(f"{period}{emoji}{signal} {summary}")
            if parts:
                lines.append(f"  {name}")
                for p in parts:
                    lines.append(f"    {p}")

        if not lines:
            return {'text': ''}

        text = "🔭 盯盘分析\n" + "\n".join(lines)
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

            lines = ['📈 市场行情']
            for region in regions:
                key = region['key']
                region_indices = indices.get(key, [])
                parts = []
                for idx in region_indices:
                    if idx.get('close') is None:
                        continue
                    pct = idx.get('change_percent')
                    pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                    parts.append(f"{idx['name']} {idx['close']:,.0f}({pct_str})")
                if parts:
                    lines.append(f"{region['name']}: {' '.join(parts)}")

            return '\n'.join(lines) if len(lines) > 1 else ''
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

            parts = []
            for f in futures:
                if f.get('close') is None:
                    continue
                pct = f.get('change_percent')
                pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                parts.append(f"{f['name']} {f['close']:,.2f}({pct_str})")

            return f"期货: {' '.join(parts)}" if parts else ''
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

            signal_map = {'buy': '🟢适合买入', 'sell': '🔴溢价过高', 'normal': '正常'}
            parts = []
            for etf in etfs:
                if etf.get('premium_rate') is None:
                    continue
                signal = signal_map.get(etf.get('signal', ''), '')
                parts.append(f"{etf['name']} {etf['premium_rate']:+.2f}%{signal}")

            return f"ETF溢价: {' | '.join(parts)}" if parts else ''
        except Exception as e:
            logger.warning(f'[通知.ETF溢价] 格式化失败: {e}')
            return ''

    @staticmethod
    def format_sectors_summary() -> str:
        """格式化板块涨跌用于推送"""
        try:
            from app.services.briefing import BriefingService

            lines = ['🔥 板块热点']

            cn_sectors = BriefingService.get_cn_sectors_data()
            if cn_sectors:
                lines.append("A股:")
                for s in cn_sectors:
                    leader = f"({s['leader']})" if s.get('leader') else ''
                    lines.append(f"  {s['name']}{s['change_percent']:+.2f}%{leader}")

            us_sectors = BriefingService.get_us_sectors_data()
            if us_sectors:
                lines.append("美股:")
                for s in us_sectors:
                    lines.append(f"  {s['name']}{s['change_percent']:+.2f}%")

            return '\n'.join(lines) if len(lines) > 1 else ''
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

            parts = []
            for item in today_data:
                if item.get('avg_price') is None:
                    continue
                pct = item.get('change_pct')
                if pct is None or pct == 0:
                    pct_str = '持平'
                else:
                    pct_str = f"{pct:+.2f}%"
                parts.append(f"{item['label']} ${item['avg_price']:.2f}({pct_str})")

            return f"💾 DRAM: {' | '.join(parts)}" if parts else ''
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
            buy_group = []
            sell_group = []
            hold_group = []

            for code, info in data.items():
                name = name_map.get(code, code)
                score = info.get('score', 0)
                signal_text = info.get('signal_text', '')
                entry = (name, score)
                if '买入' in signal_text:
                    buy_group.append(entry)
                elif '卖出' in signal_text:
                    sell_group.append(entry)
                else:
                    hold_group.append(entry)

            buy_group.sort(key=lambda x: x[1], reverse=True)
            sell_group.sort(key=lambda x: x[1], reverse=True)
            hold_group.sort(key=lambda x: x[1], reverse=True)

            lines = ['📊 技术评分']
            if buy_group:
                items = ' '.join(f"{n}{s}" for n, s in buy_group)
                lines.append(f"🟢买入: {items}")
            if sell_group:
                items = ' '.join(f"{n}{s}" for n, s in sell_group)
                lines.append(f"🔴卖出: {items}")
            if hold_group:
                items = ' '.join(f"{n}{s}" for n, s in hold_group)
                lines.append(f"⚪观望: {items}")

            return '\n'.join(lines) if len(lines) > 1 else ''
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
    def format_blog_updates() -> list[str]:
        """获取新博客文章并格式化推送文本"""
        try:
            from app.services.blog_monitor_service import BlogMonitorService
            articles = BlogMonitorService.check_all_blogs()
            texts = []
            for article in articles:
                text = f"📝 {article['source_name']} 新文章\n{article['title']}"
                if article.get('summary'):
                    text += f"\n\n{article['summary']}"
                text += f"\n\n🔗 {article['url']}"
                texts.append(text)
            return texts
        except Exception as e:
            logger.warning(f'[通知.博客监控] 获取失败: {e}')
            return []

    @staticmethod
    def format_esports_summary_split() -> tuple[str, str]:
        """格式化赛事资讯，分别返回 NBA 和 LoL 文本

        Returns:
            (nba_text, lol_text)，获取失败的部分返回空字符串
        """
        from app.config.esports_config import ESPORTS_ENABLED
        if not ESPORTS_ENABLED:
            return '', ''

        nba_text = ''
        lol_text = ''

        try:
            from app.services.esports_service import EsportsService

            # NBA
            nba = EsportsService.get_nba_schedule()
            if nba is not None:
                nba_text = NotificationService._format_nba_section(nba)

            # LoL
            lol = EsportsService.get_lol_schedule()
            if lol is not None:
                lol_sections = []
                for league_name in ['LPL', 'LCK', '先锋赛', 'Worlds', 'MSI']:
                    if league_name not in lol:
                        continue
                    league_data = lol[league_name]
                    if league_data is None:
                        lol_sections.append(f'🎮 {league_name}\n数据获取失败')
                    else:
                        section = NotificationService._format_lol_section(
                            league_name, league_data,
                        )
                        lol_sections.append(section)
                if lol_sections:
                    lol_text = '\n\n'.join(lol_sections)
        except Exception as e:
            logger.warning(f'[通知.赛事] 格式化失败: {e}')

        return nba_text, lol_text

    @staticmethod
    def _format_nba_section(nba_data) -> str:
        lines = ['🏀 NBA']
        for label, key in [('昨日', 'yesterday'), ('今日', 'today')]:
            games = nba_data.get(key)
            if games is None:
                lines.append(f'{label}: 数据获取失败')
            elif not games:
                lines.append(f'{label}: 无赛事')
            else:
                parts = []
                for g in games:
                    if g['status'] in ('completed', 'in_progress'):
                        parts.append(f"{g['away']} {g['away_score']}-{g['home_score']} {g['home']}")
                    else:
                        parts.append(f"{g['away']} vs {g['home']} {g['start_time']}")
                lines.append(f"{label}: {' | '.join(parts)}")
        return '\n'.join(lines)

    @staticmethod
    def _format_lol_section(league_name, league_data) -> str:
        lines = [f'🎮 {league_name}']
        for label, key in [('昨日', 'yesterday'), ('今日', 'today')]:
            matches = league_data.get(key)
            if matches is None:
                lines.append(f'{label}: 数据获取失败')
            elif not matches:
                lines.append(f'{label}: 无赛事')
            else:
                parts = []
                for m in matches:
                    if m['status'] in ('completed', 'in_progress') and m['score1'] is not None:
                        parts.append(f"{m['team1']} {m['score1']}-{m['score2']} {m['team2']}")
                    else:
                        parts.append(f"{m['team1']} vs {m['team2']} {m['start_time']}")
                lines.append(f"{label}: {' | '.join(parts)}")
        return '\n'.join(lines)

    @staticmethod
    def format_research_summary() -> str:
        """格式化研报摘要用于日报推送"""
        try:
            from app.services.research_report_service import (
                RESEARCH_REPORT_ENABLED,
                ResearchReportService,
            )

            if not RESEARCH_REPORT_ENABLED:
                return ''

            cache = ResearchReportService.get_latest_cached_summary()
            if not cache:
                return ''

            lines = ['📋 研报动态']
            has_report = False
            for code, info in cache.items():
                analysis = info.get('analysis', '')
                if not analysis:
                    continue
                has_report = True
                name = info.get('name', code)
                first_line = analysis.split('\n')[0].strip()
                first_line = first_line.lstrip('#*- ').strip()
                if len(first_line) > 80:
                    first_line = first_line[:80] + '...'
                lines.append(f'• {name}: {first_line}')

            if not has_report:
                return ''

            lines.append('（完整研报已于 9:00 独立推送）')
            return '\n'.join(lines)
        except Exception as e:
            logger.warning(f'[通知.研报] 格式化失败: {e}')
            return ''

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

        from app.services.position import PositionService
        position_codes = set()
        latest_date = PositionService.get_latest_date()
        if latest_date:
            pos_list = PositionService.get_snapshot(latest_date)
            position_codes = {p.stock_code for p in pos_list}

        # 收集所有结构化数据
        briefing = NotificationService.format_briefing_summary()
        alerts = NotificationService.format_alert_signals(codes, name_map, position_codes)
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

        # 赛事资讯
        nba_text, lol_text = NotificationService.format_esports_summary_split()

        research_text = NotificationService.format_research_summary()

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

        # 组装多条消息分批发送

        # Message 1: 要点（核心观点 + 持仓 + 信号）
        msg1_parts = []
        if core_insights:
            header = f"🎯 今日核心观点\n{core_insights}"
            if action_suggestions:
                header += f"\n\n💡 {action_suggestions}"
            msg1_parts.append(header)
        elif action_suggestions:
            msg1_parts.append(f"💡 {action_suggestions}")
        msg1_parts.append(briefing['text'])
        if alerts.get('text'):
            msg1_parts.append(alerts['text'])

        # Message 2: AI分析（盯盘）
        msg2_parts = []
        if watch_text:
            msg2_parts.append(watch_text)

        # Message 3: 市场与数据
        msg3_parts = []
        market_lines = []
        if indices_text:
            market_lines.append(indices_text)
        if futures_text:
            market_lines.append(futures_text)
        if etf_text:
            market_lines.append(etf_text)
        if market_lines:
            msg3_parts.append('\n'.join(market_lines))
        if sectors_text:
            msg3_parts.append(sectors_text)
        if technical_text:
            msg3_parts.append(technical_text)
        data_lines = []
        if dram_text:
            data_lines.append(dram_text)
        if earnings.get('text'):
            data_lines.append(earnings['text'])
        if pe.get('text'):
            data_lines.append(pe['text'])
        if data_lines:
            msg3_parts.append('\n'.join(data_lines))
        if ai_text:
            msg3_parts.append(ai_text)
        if research_text:
            msg3_parts.append(research_text)

        news_messages = []
        for parts in (msg1_parts, msg3_parts):
            if parts:
                news_messages.append('\n\n'.join(parts))

        watch_msg = '\n\n'.join(msg2_parts) if msg2_parts else ''

        # 标记已推送的 GitHub Release 版本
        if release_pushed_versions:
            from app.services.github_release import GitHubReleaseService
            for key, version in release_pushed_versions:
                GitHubReleaseService.mark_pushed_version(key, version)

        # 今日核心观点 → news_daily
        if core_insights:
            daily_header = f"📅 {today.strftime('%Y-%m-%d')}\n\n🎯 今日核心观点\n{core_insights}"
            if action_suggestions:
                daily_header += f"\n\n💡 {action_suggestions}"
            NotificationService.send_slack(daily_header, CHANNEL_DAILY)

        sent = 0
        for msg in news_messages:
            if NotificationService.send_slack(msg, CHANNEL_NEWS):
                sent += 1

        if watch_msg and NotificationService.send_slack(watch_msg, CHANNEL_WATCH):
            sent += 1

        # GitHub Release + 博客监控 → news_ai_tool
        blog_texts = NotificationService.format_blog_updates()
        ai_tool_texts = release_texts + blog_texts
        if ai_tool_texts:
            ai_tool_msg = '\n\n'.join(ai_tool_texts)
            if NotificationService.send_slack(ai_tool_msg, CHANNEL_AI_TOOL):
                sent += 1

        # 赛事 → 各自频道
        if nba_text:
            if NotificationService.send_slack(nba_text, CHANNEL_NBA):
                sent += 1
        if lol_text:
            if NotificationService.send_slack(lol_text, CHANNEL_LOL):
                sent += 1

        total = len(news_messages) + (1 if watch_msg else 0)
        results = {'slack': sent > 0, 'messages_sent': sent, 'messages_total': total}
        results['content_preview'] = news_messages[0][:500] if news_messages else ''
        return results

    @staticmethod
    def push_daily_extras() -> dict:
        """周末推送: GitHub Release + 赛事资讯（不含市场简报）"""
        with NotificationService._daily_push_lock:
            today = date.today()

            if NotificationService.has_daily_push(today):
                logger.info('[通知] 今日已推送，跳过')
                return {'skipped': True}

            NotificationService._mark_daily_push(today)

        sent = 0

        # GitHub Release + 博客监控 → news_ai_tool
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
        blog_texts = NotificationService.format_blog_updates()
        ai_tool_texts = release_texts + blog_texts
        if ai_tool_texts:
            ai_tool_msg = '\n\n'.join(ai_tool_texts)
            if NotificationService.send_slack(ai_tool_msg, CHANNEL_AI_TOOL):
                sent += 1

        if release_pushed_versions:
            from app.services.github_release import GitHubReleaseService
            for key, version in release_pushed_versions:
                GitHubReleaseService.mark_pushed_version(key, version)

        # 赛事 → 各自频道
        nba_text, lol_text = NotificationService.format_esports_summary_split()
        if nba_text:
            if NotificationService.send_slack(nba_text, CHANNEL_NBA):
                sent += 1
        if lol_text:
            if NotificationService.send_slack(lol_text, CHANNEL_LOL):
                sent += 1

        return {'slack': sent > 0, 'messages_sent': sent}

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

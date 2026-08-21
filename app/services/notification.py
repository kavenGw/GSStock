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
    CHANNEL_NEWS, CHANNEL_WATCH, CHANNEL_AI_TOOL, CHANNEL_DAILY,
    CHANNEL_OPERATION,
)

logger = logging.getLogger(__name__)

# Slack section text 硬上限 3000 字，留出余量防表情/转义放大后越界
CALENDAR_SECTION_MAX_CHARS = 2800


class NotificationService:
    """消息推送服务"""

    _daily_push_lock = threading.Lock()

    @staticmethod
    def get_status() -> dict:
        return {
            'slack': SLACK_ENABLED,
        }

    _signal_state = {}  # 类变量，状态机去重
    _realtime_push_state = {'date': None, 'stocks': {}}  # 实时分析增量推送状态

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
        direction = (signal.data or {}).get('direction', '')
        if direction in ('high', 'above', 'up', 'buy', 'resistance_break'):
            emoji = '🔴'
        elif direction in ('low', 'below', 'down', 'sell', 'support_break'):
            emoji = '🟢'
        else:
            emoji = {"HIGH": "⚠️", "MEDIUM": "🟡"}.get(signal.priority, "")
        text = f"{emoji} *[{signal.strategy}]* {signal.title}"
        if signal.detail:
            text += f"\n{signal.detail}"
        STRATEGY_CHANNEL = {
            'watch_alert': CHANNEL_WATCH,
            'volume_alert': CHANNEL_DAILY,
        }
        channel = STRATEGY_CHANNEL.get(signal.strategy, CHANNEL_NEWS)
        NotificationService.send_slack(text, channel)

    @staticmethod
    def push_watch_alerts(alerts) -> bool:
        """合并盯盘告警推送：一股一条，跳过 LOW（LOW 只 debug log）"""
        pushed = 0
        for a in alerts:
            if a.priority == 'LOW':
                logger.debug(f'[盯盘告警] {a.name}({a.code}) LOW 静默: {a.primary_line}')
                continue
            chg = a.change_percent
            if chg is None:
                emoji = '⚠️'
            elif chg > 0:
                emoji = '🔴'
            elif chg < 0:
                emoji = '🟢'
            else:
                emoji = '⚪'
            parts = [emoji, f'*{a.name}({a.code})*']
            if a.current_price is not None:
                parts.append(f'{a.current_price:,.2f}'.rstrip('0').rstrip('.'))
            if chg is not None:
                parts.append(f'{chg:+.2f}%')
            lines = [f"{' '.join(parts)}  [{a.priority}]", a.primary_line]
            for s in a.secondary_lines:
                lines.append(f'  · {s}')
            if a.context_line:
                lines.append(a.context_line)
            if NotificationService.send_slack('\n'.join(lines), CHANNEL_WATCH):
                pushed += 1
        return pushed > 0

    @staticmethod
    def send_slack(message: str, channel: str = CHANNEL_NEWS, blocks: list = None) -> bool:
        if not SLACK_ENABLED:
            logger.warning('[通知.Slack] Slack 未配置')
            return False

        try:
            data = {'channel': channel, 'text': message}
            if blocks:
                data['blocks'] = blocks[:50]
            payload = json.dumps(data).encode('utf-8')
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

        _pct = NotificationService.fmt_pct
        text = f"📊 持仓 ({latest_date}) | ¥{total_market_value:,.0f} | {_pct(total_pct, digits=1)}\n"

        sorted_items = sorted(items, key=lambda x: x['profit_pct'], reverse=True)
        gainers = [i for i in sorted_items if i['profit_pct'] >= 0]
        losers = [i for i in sorted_items if i['profit_pct'] < 0]

        if gainers:
            parts = [f"{i['name']} {_pct(i['profit_pct'], digits=1)}" for i in gainers]
            text += ' | '.join(parts) + '\n'
        if losers:
            parts = [f"{i['name']} {_pct(i['profit_pct'], digits=1)}" for i in losers]
            text += ' | '.join(parts)

        return {'text': text.rstrip('\n')}

    @staticmethod
    def format_calendar_events(days: int = 7) -> str:
        """未来 N 天事件（读 stock_event 表，采集已由 calendar_event 策略在 7:30 完成）"""
        from datetime import timedelta
        from app.services.calendar_event import CalendarEventService

        try:
            today = date.today()
            events = CalendarEventService.get_events(today, today + timedelta(days=days))
            stale_hours = CalendarEventService.hours_since_refresh()
        except Exception as e:
            logger.warning(f'[通知.事件日历] 读取失败: {e}')
            return ''

        if not events:
            return ''

        header = f'📅 未来{days}天事件'
        if stale_hours is not None and stale_hours >= 24:
            header += f'（⚠️ 事件数据 {int(stale_hours)} 小时未更新）'

        lines = [header]
        last_date = None
        for e in events:
            iso = e['event_date']
            if iso == last_date:
                label = ' ' * 6
            else:
                label = '今天  ' if iso == today.isoformat() else f'{iso[5:]} '
                last_date = iso

            if e['stock_code']:
                subject = f"{e['stock_name'] or e['stock_code']}({e['stock_code']})"
                body = f"{subject} {e['title']}"
            else:
                body = e['title']

            if e.get('detail'):
                body += f" · {e['detail']}"
            elif e.get('status') == 'confirmed':
                body += ' · 已确认'

            lines.append(f'  {label}{body}')

        return NotificationService._cap_calendar_lines(lines)

    @staticmethod
    def _cap_calendar_lines(lines: list[str]) -> str:
        """按 Slack section 3000 字上限收口，超出部分折成一行「另有 N 条」

        Slack 会整条拒收 section text 超 3000 字的 chat.postMessage——不设限的话
        事件一多就是整条推送消失，而不是这一段变短。截断按行边界做，保留最早的事件。
        """
        head, body = lines[0], lines[1:]
        used = len(head)
        kept = []
        for i, line in enumerate(body):
            more = f'  …另有 {len(body) - i} 条事件未显示'
            if used + 1 + len(line) > CALENDAR_SECTION_MAX_CHARS - len(more) - 1:
                return '\n'.join([head] + kept + [more])
            used += 1 + len(line)
            kept.append(line)

        return '\n'.join([head] + kept)

    @staticmethod
    def format_earnings_alerts(codes: list[str] = None, name_map: dict[str, str] = None) -> dict:
        """生成财报日期提醒（未来7天）

        盯盘池的事件已由 format_calendar_events 覆盖，此处只报补集，避免同条消息重复。
        """
        from app.services.earnings import EarningsService
        from app.services.watch_service import WatchService

        if codes is None or name_map is None:
            codes, name_map = NotificationService._get_all_watched_codes()

        # 排除集需并上 A+H 对应代码：日历段按 WATCH_CODES 顶层代码报（不展开 ah，
        # 否则同公司会在日历段内部重复），但推送层要防的是"同公司被两个段落各报一次"，
        # 所以这里反过来要展开——两边故意不对称，勿"统一"。见 calendar_event._watch_entries
        # （那里还记了第三处：简报页 BriefingService.get_earnings_alert_data 走合并口径）。
        watch_codes = set(WatchService.get_watch_codes_with_ah())
        target_codes = [c for c in codes if c not in watch_codes]

        if not target_codes:
            return {'text': ''}

        upcoming = EarningsService.get_upcoming_earnings(target_codes, days=7)
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
    def _normalize_levels(levels):
        """归一化支撑/压力位用于比较"""
        if not levels:
            return []
        return sorted(round(float(lv), 2) for lv in levels if lv is not None)

    @staticmethod
    def _detect_realtime_changes(code: str, data: dict) -> tuple:
        """检测实时分析相对上次推送的变化。返回 (is_first, changes_dict)"""
        state = NotificationService._realtime_push_state
        today = datetime.now().strftime('%Y-%m-%d')
        if state['date'] != today:
            state['date'] = today
            state['stocks'] = {}

        current = {
            'signal': data.get('signal', ''),
            'support_levels': NotificationService._normalize_levels(data.get('support_levels', [])),
            'resistance_levels': NotificationService._normalize_levels(data.get('resistance_levels', [])),
            'summary': data.get('summary', ''),
        }

        prev = state['stocks'].get(code)
        if prev is None:
            return True, current

        changes = {}
        if current['signal'] != prev['signal']:
            changes['signal'] = prev['signal']
        if current['support_levels'] != prev['support_levels']:
            changes['support'] = True
        if current['resistance_levels'] != prev['resistance_levels']:
            changes['resistance'] = True
        if current['summary'] != prev['summary']:
            changes['summary'] = True
        return False, changes

    @staticmethod
    def push_realtime_analysis(analyses: dict) -> bool:
        """推送盯盘实时分析结果到 Slack（首次完整，后续仅推变化）"""
        if not analyses:
            return False

        from app.services.watch_service import WatchService
        watch_list = WatchService.get_watch_list()
        name_map = {w['stock_code']: w['stock_name'] for w in watch_list}

        signal_icons = {'buy': '🔴买入', 'sell': '🟢卖出', 'hold': '🟡持有', 'watch': '⚪观望'}
        now_str = datetime.now().strftime('%H:%M')

        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.price_freshness import filter_fresh_prices
        all_codes = [c for c, p in analyses.items() if p.get('realtime')]
        raw_prices = unified_stock_data_service.get_realtime_prices(
            all_codes, cache_only=True) if all_codes else {}
        market_map = {w['stock_code']: w['market'] for w in watch_list}
        raw_prices = filter_fresh_prices(raw_prices, market_map)

        def _fmt_levels(levels, current):
            if not levels or current is None:
                return ' / '.join(str(s) for s in levels) if levels else '-'
            parts = []
            for lv in levels:
                try:
                    dist = (lv - current) / current * 100
                    parts.append(f"{lv}({dist:+.1f}%)")
                except (TypeError, ZeroDivisionError):
                    parts.append(str(lv))
            return ' / '.join(parts)

        full_blocks = []
        update_blocks = []
        stale_skipped = []

        for code, periods in analyses.items():
            data = periods.get('realtime')
            if not data:
                continue

            if code not in raw_prices:
                stale_skipped.append(code)
                continue

            is_first, changes = NotificationService._detect_realtime_changes(code, data)

            if not is_first and not changes:
                continue

            name = name_map.get(code, code)
            signal_key = data.get('signal', '')
            signal = signal_icons.get(signal_key, '⚪观望')
            summary = data.get('summary', '')
            price_data = raw_prices[code]
            current_price = price_data.get('current_price')
            change_pct = price_data.get('change_percent')
            support = data.get('support_levels', [])
            resistance = data.get('resistance_levels', [])
            sup_str = _fmt_levels(support, current_price)
            res_str = _fmt_levels(resistance, current_price)

            # 记录本次推送状态
            NotificationService._realtime_push_state['stocks'][code] = {
                'signal': signal_key,
                'support_levels': NotificationService._normalize_levels(support),
                'resistance_levels': NotificationService._normalize_levels(resistance),
                'summary': summary,
            }

            if is_first:
                lines = [f"{signal} {name}({code})"]
                pct_str = NotificationService.fmt_pct(change_pct, none='')
                lines.append(f"  现价 {current_price} {pct_str} | 支撑 {sup_str} | 压力 {res_str}")
                lines.append(f"  💡 {summary}")
                full_blocks.append("\n".join(lines))
            else:
                old_signal = changes.get('signal')
                header = f"{signal} {name}({code})"
                if old_signal is not None:
                    old_label = signal_icons.get(old_signal, old_signal)
                    header += f"  <- {old_label}"
                lines = [header]
                pct_str = NotificationService.fmt_pct(change_pct, none='')
                lines.append(f"  现价 {current_price} {pct_str}")
                if changes.get('support'):
                    lines.append(f"  支撑 {sup_str} -> 调整")
                if changes.get('resistance'):
                    lines.append(f"  压力 {res_str} -> 调整")
                if changes.get('summary'):
                    lines.append(f"  💡 {summary}")
                update_blocks.append("\n".join(lines))

        if stale_skipped:
            logger.info(f'[盯盘实时] 推送跳过{len(stale_skipped)}只降级/超龄旧价: {stale_skipped}')

        sent = False
        separator = "\n——————————————————\n"
        if full_blocks:
            msg = f"📊 盯盘实时分析 ({now_str})\n——————————————————\n" + separator.join(full_blocks)
            sent = NotificationService.send_slack(msg, CHANNEL_WATCH) or sent
        if update_blocks:
            msg = f"🔄 盯盘更新 ({now_str})\n——————————————————\n" + separator.join(update_blocks)
            sent = NotificationService.send_slack(msg, CHANNEL_WATCH) or sent
        if not full_blocks and not update_blocks:
            logger.info('[盯盘实时] 分析无变化，跳过推送')
        return sent

    @staticmethod
    def format_watch_analysis(analyses: dict) -> dict:
        """格式化盯盘AI分析结果用于推送"""
        if not analyses:
            return {'text': ''}

        from app.services.watch_service import WatchService
        watch_list = WatchService.get_watch_list()
        name_map = {w['stock_code']: w['stock_name'] for w in watch_list}

        signal_emoji = {'buy': '🔴', 'sell': '🟢', 'hold': '🟡'}
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
                    parts.append(f"{idx['name']} {idx['close']:,.0f} {NotificationService.fmt_pct(pct)}")
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
                parts.append(f"{f['name']} {f['close']:,.2f} {NotificationService.fmt_pct(pct)}")

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

            signal_map = {'buy': '🔴适合买入', 'sell': '🟢溢价过高', 'normal': '正常'}
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
    def format_adr_premium_summary() -> str:
        """格式化 ADR 跨市场溢价用于推送"""
        try:
            from app.services.briefing import BriefingService
            data = BriefingService.get_adr_premium_data()
            pairs = data.get('pairs', [])
            if not pairs:
                return ''

            parts = []
            any_valid = False
            for p in pairs:
                pr = p.get('premium_rate')
                if pr is None:
                    parts.append(f"{p['name']} —")
                    continue
                any_valid = True
                tag = '溢价' if pr >= 0 else '折价'
                seg = f"{p['name']} {pr:+.2f}%({tag})"
                delta = p.get('delta')
                if delta is not None and delta != 0:
                    arrow = '↑' if delta > 0 else '↓'
                    seg += f"{arrow}{abs(delta):.1f}pct"
                parts.append(seg)

            return f"🌏 ADR溢价: {' | '.join(parts)}" if any_valid else ''
        except Exception as e:
            logger.warning(f'[通知.ADR溢价] 格式化失败: {e}')
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
                    lines.append(f"  {s['name']} {NotificationService.fmt_pct(s['change_percent'])}{leader}")

            us_sectors = BriefingService.get_us_sectors_data()
            if us_sectors:
                lines.append("美股:")
                for s in us_sectors:
                    lines.append(f"  {s['name']} {NotificationService.fmt_pct(s['change_percent'])}")

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
                pct_str = '持平' if (pct is None or pct == 0) else NotificationService.fmt_pct(pct)
                parts.append(f"{item['label']} ${item['avg_price']:.2f} {pct_str}")

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
                lines.append(f"🔴买入: {items}")
            if sell_group:
                items = ' '.join(f"{n}{s}" for n, s in sell_group)
                lines.append(f"🟢卖出: {items}")
            if hold_group:
                items = ' '.join(f"{n}{s}" for n, s in hold_group)
                lines.append(f"⚪观望: {items}")

            return '\n'.join(lines) if len(lines) > 1 else ''
        except Exception as e:
            logger.warning(f'[通知.技术评分] 格式化失败: {e}')
            return ''

    @staticmethod
    def _format_release_block(name: str, emoji: str, version_data: dict) -> str:
        """渲染单个 version 的 Slack mrkdwn 文本块

        Args:
            name: 项目名（如 "Claude Code"）
            emoji: 项目 emoji（如 "🤖"）
            version_data: {version, date, features, fixes}
        """
        version = version_data.get('version', '')
        date = version_data.get('date', '')
        features = version_data.get('features') or []
        fixes = version_data.get('fixes') or []

        lines = [f"{emoji} *{name} {version}* ({date})"]
        if features:
            lines.append('')
            lines.append('✨ *新功能*')
            lines.extend(f"• {item}" for item in features)
        if fixes:
            lines.append('')
            lines.append('🐛 *修复*')
            lines.extend(f"• {item}" for item in fixes)
        return '\n'.join(lines)

    @staticmethod
    def format_github_release_updates() -> tuple[list[str], list[tuple[str, str]]]:
        """格式化所有 GitHub 仓库的版本更新摘要

        Returns:
            (texts, pushed_versions)
            - texts: 每个有更新的仓库一段文本（分类 bullet 结构）
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
                release_url = releases[0].get('url', '')
                has_body = any(r.get('body', '').strip() for r in releases)

                rendered = None
                if has_body:
                    rendered = NotificationService._render_release_categorized(cfg, releases)

                if rendered:
                    text = rendered
                    if release_url:
                        text += f"\n\n🔗 {release_url}"
                    texts.append(text)
                else:
                    # 降级：纯文本（含 changelog 截断）
                    texts.append(NotificationService._render_release_fallback(cfg, releases, release_url))
        except Exception as e:
            logger.warning(f'[通知.GitHub Release更新] 获取失败: {e}')

        return texts, pushed_versions

    @staticmethod
    def _render_release_categorized(cfg: dict, releases: list[dict]) -> str | None:
        """调 LLM + 解析 JSON + 装组分类 bullet。失败返回 None。"""
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.github_release_update import (
                GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT, build_github_release_update_prompt,
            )

            provider = llm_router.route('github_release_update')
            if not provider:
                return None

            prompt = build_github_release_update_prompt(cfg['name'], releases)
            raw = provider.chat(
                [
                    {'role': 'system', 'content': GITHUB_RELEASE_UPDATE_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )

            data = json.loads(raw.strip())
            versions = data.get('versions') or []
            if not versions:
                logger.warning(f"[通知.{cfg['name']}更新] LLM 返回 versions 为空，降级")
                return None

            # 至少要有一个 version 含 features 或 fixes，否则降级
            if not any((v.get('features') or v.get('fixes')) for v in versions):
                logger.warning(f"[通知.{cfg['name']}更新] LLM 分类全空，降级")
                return None

            blocks = [
                NotificationService._format_release_block(cfg['name'], cfg['emoji'], v)
                for v in versions
            ]
            return '\n\n'.join(blocks)

        except json.JSONDecodeError as e:
            logger.warning(f"[通知.{cfg['name']}更新] LLM JSON 解析失败: {e}，降级")
            return None
        except Exception as e:
            logger.warning(f"[通知.{cfg['name']}更新] LLM 调用失败: {e}，降级")
            return None

    @staticmethod
    def _render_release_fallback(cfg: dict, releases: list[dict], release_url: str) -> str:
        """降级路径：纯文本 changelog 截断"""
        lines = [f"{cfg['emoji']} {cfg['name']} 更新"]
        for r in releases:
            lines.append(f"{r['version']} ({r['published_at']})")
            if r.get('body'):
                body = r['body'].strip()
                if len(body) > 500:
                    body = body[:500] + '…'
                lines.append(body)
        if release_url:
            lines.append(f"\n🔗 {release_url}")
        return '\n'.join(lines)

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
    def format_github_trending_updates() -> list[str]:
        """获取 GitHub Trending 新上榜项目并格式化推送文本"""
        try:
            from app.services.github_trending_service import GitHubTrendingService
            repos = GitHubTrendingService.fetch_trending()
            if not repos:
                return []

            lines = [f'🔥 *GitHub Trending 新上榜（{len(repos)}个）*']
            for repo in repos:
                lines.append('')
                lines.append('─' * 30)
                lines.append(f"📦 *{repo['full_name']}*")
                star_parts = []
                if repo['stars']:
                    star_parts.append(f"⭐ {repo['stars']:,}")
                if repo['today_stars']:
                    star_parts.append(f"📈 今日 +{repo['today_stars']:,}")
                if star_parts:
                    lines.append(' │ '.join(star_parts))
                lines.append('')
                if repo.get('summary'):
                    lines.append(repo['summary'])
                elif repo['description']:
                    lines.append(repo['description'])
                lines.append(f"🔗 {repo['url']}")

            return ['\n'.join(lines)]
        except Exception as e:
            logger.warning(f'[通知.GitHub Trending] 获取失败: {e}')
            return []

    # ── Slack Block Kit helpers ──

    @staticmethod
    def _block_header(text: str) -> dict:
        return {'type': 'header', 'text': {'type': 'plain_text', 'text': text, 'emoji': True}}

    @staticmethod
    def _block_section(text: str) -> dict:
        return {'type': 'section', 'text': {'type': 'mrkdwn', 'text': text}}

    @staticmethod
    def _block_divider() -> dict:
        return {'type': 'divider'}

    @staticmethod
    def _block_fields(fields: list[str]) -> dict:
        return {
            'type': 'section',
            'fields': [{'type': 'mrkdwn', 'text': f} for f in fields[:10]],
        }

    @staticmethod
    def fmt_pct(pct, digits=2, code=False, none='—') -> str:
        """涨跌幅统一渲染：红涨绿跌，色块紧贴百分比。仅用于价格涨跌/盈亏，
        溢价折价、距离支撑等语义不同的百分比不得走此函数。"""
        if pct is None:
            return none
        if pct > 0:
            dot, s = '🔴', f"{pct:+.{digits}f}%"
        elif pct < 0:
            dot, s = '🟢', f"{pct:+.{digits}f}%"
        else:
            dot, s = '⚪', f"{0:.{digits}f}%"
        return f"{dot}`{s}`" if code else f"{dot}{s}"

    @staticmethod
    def build_briefing_blocks(briefing_text: str, core_insights: str = '',
                              action_suggestions: str = '') -> list:
        """构建 Message 1 的 Block Kit blocks（核心观点 + 持仓）"""
        B = NotificationService
        blocks = []

        if core_insights:
            blocks.append(B._block_header('🎯 今日核心观点'))
            text = core_insights
            if action_suggestions:
                text += f"\n\n💡 {action_suggestions}"
            blocks.append(B._block_section(text))
            blocks.append(B._block_divider())

        if briefing_text:
            for line in briefing_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('📊'):
                    blocks.append(B._block_header(line))
                elif '🟢' in line or '🔴' in line:
                    items = [x.strip() for x in line.split(' | ') if x.strip()]
                    if len(items) > 1:
                        blocks.append(B._block_fields(items))
                    else:
                        blocks.append(B._block_section(line))
                else:
                    blocks.append(B._block_section(line))

        return blocks

    @staticmethod
    def _fmt_index_item(idx: dict) -> str:
        """格式化单个指数/期货项为 mrkdwn"""
        name = idx.get('name', '')
        close = idx.get('close')
        pct = idx.get('change_percent')
        if close is None:
            return ''
        close_str = f"{close:,.0f}" if close >= 100 else f"{close:,.2f}"
        if pct is not None:
            return f"{name}  {close_str}  {NotificationService.fmt_pct(pct, code=True)}"
        return f"{name}  {close_str}"

    @staticmethod
    def build_market_blocks(indices_text: str, futures_text: str, etf_text: str,
                            sectors_text: str, technical_text: str,
                            dram_text: str = '', earnings_text: str = '',
                            ai_text: str = '',
                            adr_text: str = '', calendar_text: str = '') -> list:
        """构建 Message 3 的 Block Kit blocks（市场行情 + 板块 + 技术 + 数据）"""
        B = NotificationService
        blocks = []

        # 市场行情 - 从 BriefingService 获取结构化数据
        has_market = indices_text or futures_text or etf_text or adr_text
        if has_market:
            blocks.append(B._block_header('📈 市场行情'))

        try:
            from app.services.briefing import BriefingService
            idx_data = BriefingService.get_indices_data()
            regions = idx_data.get('regions', [])
            indices = idx_data.get('indices', {})
            for region in regions:
                key = region['key']
                region_indices = indices.get(key, [])
                items = [B._fmt_index_item(idx) for idx in region_indices if idx.get('close') is not None]
                if items:
                    blocks.append(B._block_section(f"*{region['name']}*"))
                    for i in range(0, len(items), 2):
                        blocks.append(B._block_fields(items[i:i+2]))
        except Exception:
            if indices_text:
                for line in indices_text.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('📈'):
                        blocks.append(B._block_section(line))

        try:
            from app.services.briefing import BriefingService
            fut_data = BriefingService.get_futures_data()
            futures = fut_data.get('futures', [])
            items = [B._fmt_index_item(f) for f in futures if f.get('close') is not None]
            if items:
                blocks.append(B._block_section('*期货*'))
                for i in range(0, len(items), 2):
                    blocks.append(B._block_fields(items[i:i+2]))
        except Exception:
            if futures_text:
                blocks.append(B._block_section(futures_text))

        try:
            from app.services.briefing import BriefingService
            etf_data = BriefingService.get_etf_premium_data()
            etfs = etf_data.get('etfs', [])
            signal_map = {'buy': '🔴 适合买入', 'sell': '🟢 溢价过高', 'normal': '正常'}
            items = []
            for etf in etfs:
                if etf.get('premium_rate') is None:
                    continue
                sig = signal_map.get(etf.get('signal', ''), '')
                items.append(f"{etf['name']}  `{etf['premium_rate']:+.2f}%`  {sig}")
            if items:
                blocks.append(B._block_section('*ETF溢价*'))
                blocks.append(B._block_fields(items))
        except Exception:
            if etf_text:
                blocks.append(B._block_section(etf_text))

        try:
            from app.services.briefing import BriefingService
            adr_data = BriefingService.get_adr_premium_data()
            items = []
            for p in adr_data.get('pairs', []):
                pr = p.get('premium_rate')
                if pr is None:
                    items.append(f"{p['name']}  `—`")
                    continue
                tag = '溢价' if pr >= 0 else '折价'
                seg = f"{p['name']}  `{pr:+.2f}%`  {tag}"
                delta = p.get('delta')
                if delta is not None and delta != 0:
                    seg += f" {'↑' if delta > 0 else '↓'}{abs(delta):.1f}pct"
                items.append(seg)
            if items:
                blocks.append(B._block_section('*ADR溢价*'))
                blocks.append(B._block_fields(items))
        except Exception:
            if adr_text:
                blocks.append(B._block_section(adr_text))

        # 板块热点
        if sectors_text:
            blocks.append(B._block_divider())
            try:
                from app.services.briefing import BriefingService
                blocks.append(B._block_header('🔥 板块热点'))
                cn_sectors = BriefingService.get_cn_sectors_data()
                if cn_sectors:
                    items = []
                    for s in cn_sectors:
                        leader = f"({s['leader']})" if s.get('leader') else ''
                        pct = s['change_percent']
                        items.append(f"{s['name']}  {B.fmt_pct(pct, code=True)} {leader}")
                    blocks.append(B._block_section('*A股*'))
                    for i in range(0, len(items), 2):
                        blocks.append(B._block_fields(items[i:i+2]))
                us_sectors = BriefingService.get_us_sectors_data()
                if us_sectors:
                    items = []
                    for s in us_sectors:
                        pct = s['change_percent']
                        items.append(f"{s['name']}  {B.fmt_pct(pct, code=True)}")
                    blocks.append(B._block_section('*美股*'))
                    for i in range(0, len(items), 2):
                        blocks.append(B._block_fields(items[i:i+2]))
            except Exception:
                for line in sectors_text.split('\n'):
                    line = line.strip()
                    if line and not line.startswith('🔥'):
                        blocks.append(B._block_section(line))

        # 技术评分
        if technical_text:
            blocks.append(B._block_divider())
            for line in technical_text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                if line.startswith('📊'):
                    blocks.append(B._block_header(line))
                elif line.startswith(('🟢', '🔴', '⚪')):
                    colon = line.find(':')
                    if colon > 0:
                        label = line[:colon + 1].strip()
                        items = line[colon + 1:].strip().split()
                        item_text = '  '.join(f"`{it}`" for it in items)
                        blocks.append(B._block_section(f"*{label}* {item_text}"))
                    else:
                        blocks.append(B._block_section(line))
                else:
                    blocks.append(B._block_section(line))

        # 日历 / DRAM / 财报
        extra_texts = [t for t in [calendar_text, dram_text, earnings_text] if t]
        if extra_texts:
            blocks.append(B._block_divider())
            for t in extra_texts:
                for line in t.split('\n'):
                    line = line.strip()
                    if line:
                        blocks.append(B._block_section(line))

        if ai_text:
            blocks.append(B._block_divider())
            blocks.append(B._block_section(ai_text[:3000]))

        return blocks

    @staticmethod
    def push_daily_report(include_ai: bool = False) -> dict:
        """一键推送每日报告（持仓+简报数据+GLM总结+盯盘分析）"""
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
        earnings = NotificationService.format_earnings_alerts(codes, name_map)

        indices_text = NotificationService.format_indices_summary()
        futures_text = NotificationService.format_futures_summary()
        etf_text = NotificationService.format_etf_premium_summary()
        adr_text = NotificationService.format_adr_premium_summary()
        sectors_text = NotificationService.format_sectors_summary()
        dram_text = NotificationService.format_dram_summary()
        technical_text = NotificationService.format_technical_summary()
        calendar_text = NotificationService.format_calendar_events()

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
                    'adr_premium': adr_text,
                    'sectors': sectors_text,
                    'dram': dram_text,
                    'technical': technical_text,
                    'calendar_events': calendar_text,
                    'earnings_alerts': earnings.get('text', ''),
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

        # 组装纯文本（fallback）+ Block Kit blocks

        # Message 1: 要点（核心观点 + 持仓）
        msg1_parts = []
        if core_insights:
            header = f"🎯 今日核心观点\n{core_insights}"
            if action_suggestions:
                header += f"\n\n💡 {action_suggestions}"
            msg1_parts.append(header)
        elif action_suggestions:
            msg1_parts.append(f"💡 {action_suggestions}")
        msg1_parts.append(briefing['text'])

        msg1_blocks = NotificationService.build_briefing_blocks(
            briefing['text'], core_insights, action_suggestions)

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
        if adr_text:
            market_lines.append(adr_text)
        if market_lines:
            msg3_parts.append('\n'.join(market_lines))
        if sectors_text:
            msg3_parts.append(sectors_text)
        if technical_text:
            msg3_parts.append(technical_text)
        data_lines = []
        if calendar_text:
            data_lines.append(calendar_text)
        if dram_text:
            data_lines.append(dram_text)
        if earnings.get('text'):
            data_lines.append(earnings['text'])
        if data_lines:
            msg3_parts.append('\n'.join(data_lines))
        if ai_text:
            msg3_parts.append(ai_text)

        msg3_blocks = NotificationService.build_market_blocks(
            indices_text=indices_text, futures_text=futures_text, etf_text=etf_text,
            sectors_text=sectors_text, technical_text=technical_text,
            dram_text=dram_text, earnings_text=earnings.get('text', ''),
            ai_text=ai_text, adr_text=adr_text, calendar_text=calendar_text)

        news_messages = []
        news_blocks_list = []
        for parts, blks in ((msg1_parts, msg1_blocks), (msg3_parts, msg3_blocks)):
            if parts:
                news_messages.append('\n\n'.join(parts))
                news_blocks_list.append(blks if blks else None)

        watch_msg = '\n\n'.join(msg2_parts) if msg2_parts else ''

        # 今日核心观点 → news_daily
        if core_insights:
            daily_text = f"📅 {today.strftime('%Y-%m-%d')}\n\n🎯 今日核心观点\n{core_insights}"
            if action_suggestions:
                daily_text += f"\n\n💡 {action_suggestions}"
            daily_blocks = [
                NotificationService._block_header(f"📅 {today.strftime('%Y-%m-%d')}"),
                NotificationService._block_header('🎯 今日核心观点'),
                NotificationService._block_section(core_insights),
            ]
            if action_suggestions:
                daily_blocks.append(NotificationService._block_section(f"💡 {action_suggestions}"))
            NotificationService.send_slack(daily_text, CHANNEL_DAILY, blocks=daily_blocks)

        sent = 0
        for i, msg in enumerate(news_messages):
            blks = news_blocks_list[i] if i < len(news_blocks_list) else None
            if NotificationService.send_slack(msg, CHANNEL_DAILY, blocks=blks):
                sent += 1

        if watch_msg and NotificationService.send_slack(watch_msg, CHANNEL_WATCH):
            sent += 1

        # GitHub Release → news_ai_tool（博客/Trending 已独立调度）
        ai_tool_texts = release_texts
        if ai_tool_texts:
            ai_tool_msg = '\n\n'.join(ai_tool_texts)
            if NotificationService.send_slack(ai_tool_msg, CHANNEL_AI_TOOL):
                sent += 1
                if release_pushed_versions:
                    from app.services.github_release import GitHubReleaseService
                    for key, version in release_pushed_versions:
                        GitHubReleaseService.mark_pushed_version(key, version)

        total = len(news_messages) + (1 if watch_msg else 0)
        results = {'slack': sent > 0, 'messages_sent': sent, 'messages_total': total}
        results['content_preview'] = news_messages[0][:500] if news_messages else ''

        try:
            from app.services.briefing import BriefingService
            BriefingService.save_adr_premium_snapshot()
        except Exception as e:
            logger.warning(f'[通知.ADR溢价] 昨日基准更新失败: {e}')

        return results

    @staticmethod
    def push_daily_extras() -> dict:
        """周末推送: GitHub Release（不含市场简报；赛事归 esports_daily_schedule 07:00）"""
        with NotificationService._daily_push_lock:
            today = date.today()

            if NotificationService.has_daily_push(today):
                logger.info('[通知] 今日已推送，跳过')
                return {'skipped': True}

            NotificationService._mark_daily_push(today)

        sent = 0

        # GitHub Release → news_ai_tool（博客/Trending 已独立调度）
        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()
        ai_tool_texts = release_texts
        if ai_tool_texts:
            ai_tool_msg = '\n\n'.join(ai_tool_texts)
            if NotificationService.send_slack(ai_tool_msg, CHANNEL_AI_TOOL):
                sent += 1
                if release_pushed_versions:
                    from app.services.github_release import GitHubReleaseService
                    for key, version in release_pushed_versions:
                        GitHubReleaseService.mark_pushed_version(key, version)

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

"""事件日历服务 — 采集并物化盯盘股/宏观重要事件"""
import calendar as _calmod
import json
import logging
import time
from datetime import date, datetime

import akshare as ak
import pandas as pd

from app import db
from app.config.macro_calendar import MACRO_EVENTS
from app.config.stock_codes import WATCH_CODES
from app.models.stock_event import StockEvent
from app.services.circuit_breaker import circuit_breaker
from app.services.earnings import (
    EarningsService, period_keys_for_window, _cell_date,
)
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)

PRIORITY_ORDER = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}

YF_MAX_RETRIES = 3
YF_RETRY_DELAY = 1.0

# period_key 后缀 -> 财报中文标题
_REPORT_TITLE = {'A': '年报披露', 'Q1': '一季报披露', 'H1': '中报披露', 'Q3': '三季报披露'}

_MACRO_SOURCE = {'fomc': 'fomc', 'cpi': 'bls', 'nfp': 'bls'}
_MACRO_MARKET = {'fomc': 'US', 'cpi': 'US', 'nfp': 'US'}

_WRITABLE_FIELDS = ('event_date', 'stock_name', 'market', 'title',
                    'detail', 'priority', 'status')

# collector -> 它负责的 source 集合（决定 prune 的作用域）
_COLLECTOR_SOURCES = {
    'earnings_a': ['cninfo'],
    'calendar_yf': ['yfinance'],
    'dividend_a': ['akshare'],
    'macro': ['fomc', 'bls'],
}


class CalendarEventService:
    """事件日历服务"""

    @staticmethod
    def upsert_events(events: list[dict]) -> list[int]:
        """按业务键 (event_type, stock_code, source, period_key) upsert，返回命中行 id"""
        ids = []
        for e in events:
            key = {
                'event_type': e['event_type'],
                'stock_code': e.get('stock_code') or '',
                'source': e['source'],
                'period_key': e['period_key'],
            }
            row = StockEvent.query.filter_by(**key).first()
            if row is None:
                row = StockEvent(**key)
                db.session.add(row)

            for f in _WRITABLE_FIELDS:
                if f in e:
                    setattr(row, f, e[f])
            extra = e.get('extra')
            row.extra = json.dumps(extra, ensure_ascii=False) if extra else None
            row.updated_at = datetime.now()

            db.session.flush()
            ids.append(row.id)

        db.session.commit()
        return ids

    @staticmethod
    def prune_stale(start: date, end: date, keep_ids: list[int],
                    sources: list[str]) -> int:
        """删除窗口内、属于 sources、且本轮未命中的行。manual 永不删除。"""
        if not sources:
            return 0

        q = StockEvent.query.filter(
            StockEvent.source.in_(sources),
            StockEvent.source != 'manual',
            StockEvent.event_date >= start,
            StockEvent.event_date <= end,
        )
        if keep_ids:
            q = q.filter(~StockEvent.id.in_(keep_ids))

        n = q.delete(synchronize_session=False)
        db.session.commit()
        return n

    @staticmethod
    def get_events(start: date, end: date) -> list[dict]:
        rows = StockEvent.query.filter(
            StockEvent.event_date >= start,
            StockEvent.event_date <= end,
        ).all()
        rows.sort(key=lambda r: (r.event_date,
                                 PRIORITY_ORDER.get(r.priority, 1),
                                 r.stock_code or ''))
        return [r.to_dict() for r in rows]

    @staticmethod
    def hours_since_refresh() -> float | None:
        """距最近一次采集的小时数；表为空返回 None"""
        latest = db.session.query(db.func.max(StockEvent.updated_at)).scalar()
        if not latest:
            return None
        return (datetime.now() - latest).total_seconds() / 3600

    @staticmethod
    def window(today: date = None) -> tuple[date, date]:
        """采集窗口：上月初 ~ 下下月末（比页面展示的双月略宽，避免边界反复增删）"""
        if today is None:
            today = date.today()

        y, m = today.year, today.month
        sy, sm = (y - 1, 12) if m == 1 else (y, m - 1)
        start = date(sy, sm, 1)

        em = m + 2
        ey = y + (em - 1) // 12
        em = (em - 1) % 12 + 1
        end = date(ey, em, _calmod.monthrange(ey, em)[1])

        return start, end

    @staticmethod
    def refresh_all(today: date = None) -> dict:
        """跑全部 collector 并物化。

        prune 的授权只来自 collector 自报的 complete=True（「本轮确实把它负责的每
        一份活都从源头取到了」），绝不从「没抛异常」倒推——总失败路径（熔断、全部
        ticker 重试耗尽、无报告期可取）都会正常返回空列表，据此 prune 会把该 source
        在整个窗口内的事件全部清空。complete=False 与抛异常一样，本轮不清理该 source。
        """
        if today is None:
            today = date.today()

        start, end = CalendarEventService.window(today)

        jobs = [
            ('earnings_a', lambda: collect_earnings_a(today)),
            ('calendar_yf', lambda: collect_calendar_yf(today)),
            ('dividend_a', lambda: collect_dividend_a(today)),
            ('macro', lambda: collect_macro_range(start, end)),
        ]

        events, ok_sources, errors, incomplete = [], [], [], []
        for key, fn in jobs:
            try:
                got, complete = fn()
                events.extend(got)
                if complete:
                    ok_sources.extend(_COLLECTOR_SOURCES[key])
                else:
                    incomplete.append(key)
                    logger.warning(
                        f'[事件日历] collector {key} 未完整采集，'
                        f'本轮跳过 {_COLLECTOR_SOURCES[key]} 的清理')
            except Exception as e:
                errors.append(f'{key}: {e}')
                logger.error(f'[事件日历] collector {key} 失败: {e}')

        in_window = [e for e in events if start <= e['event_date'] <= end]
        ids = CalendarEventService.upsert_events(in_window)
        removed = CalendarEventService.prune_stale(start, end, ids, ok_sources)

        stats = {'collected': len(events), 'upserted': len(ids),
                 'removed': removed, 'errors': errors, 'incomplete': incomplete}
        logger.info(f'[事件日历] 刷新完成: {stats}')
        return stats


def _watch_entries(markets: set[str] = None) -> list[dict]:
    """WATCH_CODES 顶层条目；不展开 ah 子代码（否则 A+H 同公司会在日历段内部重复）

    故意与 NotificationService.format_earnings_alerts 用的
    WatchService.get_watch_codes_with_ah() 相反：那边要展开 ah，
    防的是"同公司被日历段和财报段各报一次"。两边目标一致（一公司一提），
    机制刻意相反，勿"统一"。

    第三处是 BriefingService.get_earnings_alert_data（简报页财报预警），它跑的是
    全部分类股票而非盯盘池，用 WatchService.dedup_ah_codes 把两地代码合并成一行。
    三处口径各不相同但目标同一：一家公司只出现一次。
    """
    return [e for e in WATCH_CODES if markets is None or e.get('market') in markets]


def _yf_ticker(yf_code: str):
    """便于测试注入"""
    import yfinance as yf
    return yf.Ticker(yf_code)


def collect_earnings_a(today: date = None) -> tuple[list[dict], bool]:
    """A股财报日 — 巨潮预约披露

    返回 (events, complete)。complete=True 仅当至少有一个报告期、且每个报告期都
    真的从巨潮取到了披露表——「本窗口无报告期可取」不是「确认无事件」，不能据此清理。
    """
    if today is None:
        today = date.today()

    watch = {e['code']: e['name'] for e in _watch_entries({'A'})}
    if not watch:
        # 盯盘池里没有A股是本地配置的确定状态，不是取数失败：cninfo 遗留行应被清理
        return [], True

    periods = period_keys_for_window(today)
    if not periods:
        logger.warning('[事件日历] 本窗口无A股报告期，未接触巨潮，本轮不清理 cninfo 事件')
        return [], False

    out = []
    complete = True
    for period, period_key in periods:
        title = _REPORT_TITLE.get(period_key[4:], '财报披露')
        try:
            hits = EarningsService.fetch_disclosure_map(period)
        except Exception as e:
            logger.warning(f'[事件日历] 巨潮 {period} 取数失败: {e}')
            complete = False
            continue
        for code, name in watch.items():
            hit = hits.get(code)
            if not hit:
                continue
            out.append({
                'event_date': hit['date'],
                'event_type': 'earnings',
                'stock_code': code,
                'stock_name': name,
                'market': 'A',
                'title': title,
                'detail': hit.get('detail'),
                'priority': 'MEDIUM' if hit['status'] == 'scheduled' else 'HIGH',
                'source': 'cninfo',
                'status': hit['status'],
                'period_key': period_key,
                'extra': None,
            })
    return out, complete


def _yf_dates(value) -> list:
    """calendar 里的日期字段可能是 date 或 [date, ...]"""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = list(value)
    else:
        items = [value]
    out = []
    for v in items:
        d = _cell_date({'v': v}, 'v')
        if d:
            out.append(d)
    return out


def collect_calendar_yf(today: date = None) -> tuple[list[dict], bool]:
    """非A股财报日 + 除权日 — yfinance calendar 一次调用产出两类

    返回 (events, complete)。complete=True 仅当每只被尝试的 ticker 都拿到了可用
    calendar。熔断跳过、任一 ticker 重试耗尽、返回不可用对象，都会置 False——
    否则一次 yfinance 限流就会被 refresh_all 当成「确认无事件」，把窗口内全部
    港/美/韩财报与除权事件清空。
    """
    if today is None:
        today = date.today()

    # 注意 is_available 是**会改状态**的探针：OPEN 且过了冷却会被提升为 HALF_OPEN
    # 并返回 True。因此本函数必须同时上报 record_failure，否则只报成功会把熔断器
    # 替全 app 的其它 yfinance 消费者一起重置。
    if not circuit_breaker.is_available('yfinance'):
        logger.warning('[事件日历] yfinance 已熔断，跳过采集，本轮不清理 yfinance 事件')
        return [], False

    out = []
    ok = False
    complete = True
    for entry in _watch_entries():
        if entry.get('market') == 'A':
            continue

        code = entry['code']
        yf_code = MarketIdentifier.to_yfinance(code)
        cal = None
        exhausted = False
        for attempt in range(YF_MAX_RETRIES):
            try:
                cal = _yf_ticker(yf_code).calendar
                break
            except Exception as e:
                if attempt < YF_MAX_RETRIES - 1:
                    time.sleep(YF_RETRY_DELAY)
                else:
                    logger.warning(f'[事件日历] {code} calendar 重试耗尽: {e}')
                    exhausted = True

        if exhausted:
            circuit_breaker.record_failure('yfinance')

        if not hasattr(cal, 'get'):
            complete = False
            continue
        ok = True

        base = {
            'stock_code': code,
            'stock_name': entry.get('name'),
            'market': entry.get('market'),
            'source': 'yfinance',
            'status': 'scheduled',
            'detail': None,
            'extra': None,
        }

        for d in _yf_dates(cal.get('Earnings Date')):
            if d < today:
                continue
            out.append({**base, 'event_date': d, 'event_type': 'earnings',
                        'title': '财报披露', 'priority': 'MEDIUM',
                        'period_key': f'{d.year}Q{(d.month - 1) // 3 + 1}'})

        for d in _yf_dates(cal.get('Ex-Dividend Date')):
            if d < today:
                continue
            out.append({**base, 'event_date': d, 'event_type': 'ex_dividend',
                        'title': '除权除息', 'priority': 'LOW',
                        'period_key': f'XD{d.year}{d.month:02d}'})

    # 只在全员成功时报 success：部分失败也报成功会把刚累计的 failure_count 清零，
    # 熔断器永远跳不起来，同一场限流每天重演。
    if ok and complete:
        circuit_breaker.record_success('yfinance')
    return out, complete


def _fhps_report_dates(today: date) -> list[str]:
    """最近 4 个已结束的报告期末，格式 YYYYMMDD"""
    ends = []
    year = today.year
    for y in (year, year - 1):
        for mm, dd in ((12, 31), (9, 30), (6, 30), (3, 31)):
            d = date(y, mm, dd)
            if d <= today:
                ends.append(d.strftime('%Y%m%d'))
    return ends[:4]


def collect_dividend_a(today: date = None) -> tuple[list[dict], bool]:
    """A股除权除息日 — akshare 分红送配

    返回 (events, complete)。任一报告期取数失败即 complete=False：部分成功不足以
    为整个 akshare source 背书，否则失败那几期的既有除权事件会被 prune 掉。
    """
    if today is None:
        today = date.today()

    watch = {e['code']: e['name'] for e in _watch_entries({'A'})}
    if not watch:
        return [], True

    report_dates = _fhps_report_dates(today)
    if not report_dates:
        logger.warning('[事件日历] 无可取的分红报告期，本轮不清理 akshare 事件')
        return [], False

    out = []
    errors = []
    for report_date in report_dates:
        try:
            df = ak.stock_fhps_em(date=report_date)
        except Exception as e:
            logger.info(f'[事件日历] 分红送配 {report_date} 取数失败: {e}')
            errors.append((report_date, e))
            continue

        for _, row in df.iterrows():
            code = str(row.get('代码', '')).strip()
            if code not in watch:
                continue
            ex_date = _cell_date(row, '除权除息日')
            if not ex_date:
                continue

            ratio = row.get('现金分红-现金分红比例')
            progress = str(row.get('方案进度', '') or '').strip()
            bits = [b for b in (progress, f'每10股派 {ratio} 元'
                                if pd.notna(ratio) else '') if b]

            out.append({
                'event_date': ex_date,
                'event_type': 'ex_dividend',
                'stock_code': code,
                'stock_name': watch[code],
                'market': 'A',
                'title': '除权除息',
                'detail': ' · '.join(bits) or None,
                'priority': 'LOW',
                'source': 'akshare',
                'status': 'scheduled',
                'period_key': f'FH{report_date}',
                'extra': None,
            })

    if len(errors) == len(report_dates):
        raise RuntimeError(
            f'[事件日历] 分红送配全部 {len(report_dates)} 个报告期取数失败: '
            + '; '.join(f'{d}: {e}' for d, e in errors)
        )
    return out, not errors


def collect_macro_range(start: date, end: date) -> tuple[list[dict], bool]:
    """宏观事件 — 纯本地表，不联网，故 complete 恒为 True"""
    out = []
    for e in MACRO_EVENTS:
        d = e['date']
        if d < start or d > end:
            continue
        out.append({
            'event_date': d,
            'event_type': 'macro',
            'stock_code': '',
            'stock_name': None,
            'market': _MACRO_MARKET.get(e['type'], 'US'),
            'title': e['title'],
            'detail': None,
            'priority': 'HIGH',
            'source': _MACRO_SOURCE.get(e['type'], 'fomc'),
            'status': 'scheduled',
            'period_key': f'{d.isoformat()}-{e["type"]}',
            'extra': None,
        })
    return out, True

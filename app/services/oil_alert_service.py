"""原油新闻与行情共用持久化档位，发送成功后才推进已提醒档位。"""
import hashlib
import logging
import math
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.dialects.sqlite import insert

from app import db
from app.models.oil_alert import OilAlert

logger = logging.getLogger(__name__)
OIL_CODES = {'CL=F': 'WTI', 'BZ=F': '布伦特'}
QUOTE_MAX_AGE = 20 * 60
NEWS_MAX_AGE = 2 * 60 * 60
LOCAL_ZONE = ZoneInfo('Asia/Shanghai')
FUTURES_ZONE = ZoneInfo('America/New_York')
OIL_TOPIC = re.compile(r'原油|油价|\bWTI\b|\bBrent\b|布伦特|布油|美油|OPEC', re.I)
SUPPLY_EVENT = re.compile(
    r'库存|供[应给需]|需求|产量|增产|减产|限产|停产|复产|出口|进口|制裁|禁运|'
    r'封锁|中断|油田|油轮|输油|霍尔木兹|OPEC|EIA|API', re.I)
IMPORTANT = re.compile(
    r'涨|跌|飙升|暴挫|库存|供[应给需]|需求|产量|增产|减产|限产|停产|复产|'
    r'出口|进口|制裁|禁运|封锁|中断|油田|油轮|输油|霍尔木兹|OPEC|EIA|API', re.I)
PRICE_MOVE = re.compile(
    r'(?P<name>WTI|美油|布伦特|布油|Brent)[^。；;！!？?%％，,\n]{0,35}?'
    r'(?P<direction>下跌|上涨|跌幅|涨幅|大跌|大涨|跌|涨)'
    r'(?:扩大|收窄|达到|达|超过|超|逾|至|为|了|\s)*'
    r'(?P<pct>\d+(?:\.\d+)?)\s*[%％]', re.I)


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=LOCAL_ZONE)
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def trading_date(value: datetime) -> str:
    """Yahoo CL=F/BZ=F 的 CME 合约按纽约 18:00 开始下一交易日。"""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    local = value.astimezone(FUTURES_ZONE)
    day = local.date() + timedelta(days=int(local.hour >= 18))
    return day.isoformat()


class OilAlertService:
    @staticmethod
    def is_oil_news(content):
        return bool(OIL_TOPIC.search(content)
                    or ('石油' in content and SUPPLY_EVENT.search(content)))

    @staticmethod
    def price_moves(content):
        moves = {}
        # 同一新闻标题与正文常重复报价，按合约只取一次。
        for match in PRICE_MOVE.finditer(content):
            context = re.split(r'[。；;！!？?\n]', content[:match.end()])[-1]
            if re.search(r'预计|预测|可能|如果|上周|本周|年内|今年|上月|去年|累计', context):
                continue
            name = match['name'].lower()
            code = 'CL=F' if name in ('wti', '美油') else 'BZ=F'
            pct = float(match['pct']) * (-1 if '跌' in match['direction'] else 1)
            moves[code] = pct
        return moves

    @staticmethod
    def _enqueue(key, band, message, channel, source, expires_at, now):
        statement = insert(OilAlert).values(
            key=key, target_band=band, sent_band=0, message=message,
            channel=channel, source=source, expires_at=expires_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=['key'],
            set_={'target_band': band, 'message': message, 'channel': channel,
                  'source': source, 'expires_at': expires_at},
            where=(OilAlert.sent_band < band) & or_(OilAlert.target_band <= band,
                                                   OilAlert.expires_at <= now),
        )
        db.session.execute(statement)
        db.session.commit()

    @staticmethod
    def _enqueue_price(code, pct, day, message, source, expires_at, now):
        from app.config.notification_config import CHANNEL_WATCH
        if not math.isfinite(pct) or abs(pct) + 1e-9 < 2:
            return
        band = math.floor(abs(pct) + 1e-9)
        direction = 'up' if pct > 0 else 'down'
        OilAlertService._enqueue(
            f'price:{day}:{code}:{direction}', band, message,
            CHANNEL_WATCH, source, expires_at, now,
        )

    @staticmethod
    def process_news(items, now=None):
        from app.config.notification_config import CHANNEL_NEWS
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        for item in items:
            if not OilAlertService.is_oil_news(item.content):
                continue
            published = utc_naive(item.display_time)
            age = (now - published).total_seconds()
            if age < -300 or age > NEWS_MAX_AGE:
                logger.info('[原油提醒] 跳过新闻 id=%s reason=stale_news', item.id)
                continue
            if not IMPORTANT.search(item.content):
                continue
            item.is_interest = True
            item.matched_keywords = ','.join(sorted(set(
                filter(None, (item.matched_keywords or '').split(','))) | {'原油'}))
            moves = OilAlertService.price_moves(item.content)
            triggered = {code: pct for code, pct in moves.items() if abs(pct) >= 2}
            if triggered:
                for code, pct in triggered.items():
                    OilAlertService._enqueue_price(
                        code, pct, trading_date(published),
                        f'🛢️ 原油异动 · {OIL_CODES[code]} {pct:+.2f}%（新闻报道）\n{item.content}',
                        'news', published + timedelta(seconds=NEWS_MAX_AGE), now,
                    )
            elif not moves or SUPPLY_EVENT.search(item.content):
                normalized = re.sub(r'\s+|【|】', '', item.content).lower()
                digest = hashlib.sha256(normalized.encode()).hexdigest()
                OilAlertService._enqueue(
                    f'news:{published.date()}:{digest}', 1,
                    f'🛢️ 原油重要新闻\n{item.content}', CHANNEL_NEWS, 'news',
                    published + timedelta(seconds=NEWS_MAX_AGE), now,
                )
        db.session.commit()
        OilAlertService.deliver_pending(now)

    @staticmethod
    def process_quotes(prices, now=None):
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        for code in OIL_CODES:
            quote = prices.get(code) or {}
            try:
                source_time = datetime.fromisoformat(quote['quote_time'])
                if source_time.tzinfo is None:
                    raise ValueError('missing source timezone')
                timestamp = utc_naive(source_time)
                age = (now - timestamp).total_seconds()
                pct = float(quote['change_percent'])
                price = float(quote['current_price'])
                day = quote['trading_date']
                if (quote.get('_is_degraded') or not -60 <= age <= QUOTE_MAX_AGE
                        or day != trading_date(timestamp) or not math.isfinite(price)
                        or price <= 0):
                    raise ValueError('stale or invalid quote')
            except (KeyError, TypeError, ValueError):
                logger.info('[原油提醒] 跳过行情 code=%s reason=missing_or_stale_source_time', code)
                continue
            OilAlertService._enqueue_price(
                code, pct, day,
                f'🛢️ 原油异动 · {OIL_CODES[code]} {pct:+.2f}%\n'
                f'{price:.2f} 美元/桶 · 较前一交易日收盘价\n'
                f'报价时间 {quote["quote_time"]} · 数据源可能延迟',
                'quote', timestamp + timedelta(seconds=QUOTE_MAX_AGE), now,
            )
        OilAlertService.deliver_pending(now)

    @staticmethod
    def deliver_pending(now=None):
        from app.services.notification import NotificationService
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        keys = [row.key for row in OilAlert.query.filter(
            OilAlert.target_band > OilAlert.sent_band, OilAlert.expires_at > now,
            or_(OilAlert.lease_until.is_(None), OilAlert.lease_until <= now),
        ).all()]
        for key in keys:
            claimed = OilAlert.query.filter(
                OilAlert.key == key, OilAlert.target_band > OilAlert.sent_band,
                OilAlert.expires_at > now,
                or_(OilAlert.lease_until.is_(None), OilAlert.lease_until <= now),
            ).update({'lease_until': now + timedelta(minutes=2)}, synchronize_session=False)
            db.session.commit()
            if not claimed:
                continue
            row = db.session.get(OilAlert, key)
            band, message, channel = row.target_band, row.message, row.channel
            try:
                success = NotificationService.send_slack(message, channel)
            except Exception:
                logger.exception('[原油提醒] 发送异常 key=%s', key)
                success = False
            updates = {'lease_until': None}
            if success:
                updates.update(sent_band=band, sent_at=now)
            else:
                updates['lease_until'] = now + timedelta(minutes=1)
            OilAlert.query.filter_by(key=key).update(updates, synchronize_session=False)
            db.session.commit()
            logger.info('[原油提醒] 发送 key=%s band=%s success=%s', key, band, success)

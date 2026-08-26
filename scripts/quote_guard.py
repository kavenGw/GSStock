"""行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价。

用法一（推荐，无 sys.path 顾虑）——命令行：
    python scripts/quote_guard.py --code hk01888 --price 35.32 --volume 5000000 \
        --ts "2026-08-25 10:13:25" --shares 3151450000 --market-cap 111309214000
    通过 → 打印通过信息、exit 0；被拒 → 中文原因打到 stderr、非零退出。
    盘前需强取时加 `--allow-preopen`（只豁免"非交易时段"一条，成交量与市值自洽照查）。

用法二——在 `scripts/_xxx.py` 里 import：
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root，必须加
    from scripts.quote_guard import guard, QuoteRejected
    try:
        q = guard(quote_dict)
    except QuoteRejected as exc:
        print(f'取数被拒：{exc}')

    `python scripts/_xxx.py` 的 `sys.path[0]` 是 `scripts/` 而非 repo root，不加上面那行
    必然 `ModuleNotFoundError: No module named 'scripts'`。不想加就直接用 CLI。

时戳时区约定：tz-aware 时戳按对应市场时区换算后比较（HK=Asia/Hong_Kong、
A=Asia/Shanghai、US=America/New_York）；**naive 时戳一律按该市场本地时间解释**
（美股传 naive 即视为 ET，不做本机时区换算）。

见 stock-research references/lessons.md L24。
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, time
from zoneinfo import ZoneInfo

MIN_VOLUME = 1_000
MARKET_CAP_TOLERANCE = 0.01

MARKET_SESSIONS = {
    'HK': ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
    # A 股 14:57-15:00 是收盘集合竞价，与开盘竞价同类失败模式，一并排除
    'A': ((time(9, 30), time(11, 30)), (time(13, 0), time(14, 57))),
    'US': ((time(9, 30), time(16, 0)),),
}

MARKET_TZ = {
    'HK': 'Asia/Hong_Kong',
    'A': 'Asia/Shanghai',
    'US': 'America/New_York',
}


class QuoteRejected(Exception):
    """报价未通过守卫断言。"""


def infer_market(code: str) -> str:
    c = code.lower()
    if c.endswith('.hk'):
        return 'HK'
    if c.endswith(('.ss', '.sz')):
        return 'A'
    if c.startswith('hk'):
        return 'HK'
    if c.startswith(('sh', 'sz')):
        return 'A'
    # 裸代码（无前缀/后缀）按位数判市场：A 股 6 位、港股 4-5 位，均为纯数字；
    # 美股 ticker 是字母。缺了这一条，'603618' 会静默落到 US —— 而 US 时段
    # 是 9:30-16:00 连续一段，A 股 14:57 后的收盘快照会被**误判为盘中通过**
    # （假阳性），比报错更危险。见 lessons.md L36。
    if c.isdigit():
        return 'A' if len(c) == 6 else 'HK'
    return 'US'


def to_market_time(market: str, ts: datetime) -> datetime:
    """tz-aware 换算到市场时区；naive 按市场本地时间解释，原样返回。"""
    if ts.tzinfo is None:
        return ts
    return ts.astimezone(ZoneInfo(MARKET_TZ[market]))


def in_session(market: str, ts: datetime) -> bool:
    t = to_market_time(market, ts).time()
    return any(start <= t <= end for start, end in MARKET_SESSIONS[market])


def guard(quote: dict, *, allow_preopen: bool = False) -> dict:
    market = infer_market(quote['code'])
    ts = to_market_time(market, quote['timestamp'])
    if ts.weekday() >= 5:
        raise QuoteRejected(
            f"{quote['code']} 时戳 {ts:%Y-%m-%d %H:%M:%S} 落在周末 —— "
            '这是陈旧快照（成交量为上一交易日累计、市值自洽），不可作行情锚')
    if not in_session(market, ts):
        if not allow_preopen:
            raise QuoteRejected(
                f"{quote['code']} 时戳 {ts:%H:%M:%S} 不在 {market} 连续交易时段内 —— "
                '这是集合竞价参考价或非交易时段快照，不可作行情锚')
        quote['preopen_warning'] = '竞价参考价，不可作行情锚'
    if quote['volume'] < MIN_VOLUME:
        raise QuoteRejected(
            f"{quote['code']} 成交量仅 {quote['volume']} —— 疑为竞价挂单或停牌，不可作行情锚")
    implied = quote['price'] * quote['shares']
    cap = quote['market_cap']
    if not cap:
        raise QuoteRejected(
            f"{quote['code']} 市值缺失 —— 自洽校验无法进行")
    if abs(implied - cap) / cap > MARKET_CAP_TOLERANCE:
        raise QuoteRejected(
            f"{quote['code']} 市值不自洽：价×股本={implied:,.0f} vs 报市值={cap:,.0f} —— "
            '疑为字段索引错位')
    return quote


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description='行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价（见 lessons.md L24）')
    p.add_argument('--code', required=True, help='代码，如 hk01888 / sh600183 / NVDA')
    p.add_argument('--price', type=float, required=True, help='现价')
    p.add_argument('--volume', type=float, required=True, help='成交量（A股手/港美股股）')
    p.add_argument('--ts', required=True,
                   help='行情时戳，ISO 格式如 "2026-08-25 10:13:25"；naive 按该市场本地时间解释')
    p.add_argument('--shares', type=float, required=True, help='总股本')
    p.add_argument('--market-cap', type=float, default=0.0, help='报出的总市值（缺失即拒）')
    p.add_argument('--allow-preopen', action='store_true',
                   help='只豁免"非交易时段"一条；成交量与市值自洽照查')
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ts = datetime.fromisoformat(args.ts)
    except ValueError as exc:
        print(f'时戳解析失败：{exc}', file=sys.stderr)
        return 2
    quote = {
        'code': args.code,
        'price': args.price,
        'volume': args.volume,
        'timestamp': ts,
        'shares': args.shares,
        'market_cap': args.market_cap,
    }
    try:
        out = guard(quote, allow_preopen=args.allow_preopen)
    except QuoteRejected as exc:
        print(f'取数被拒：{exc}', file=sys.stderr)
        return 1
    market = infer_market(args.code)
    implied = args.price * args.shares
    dev = abs(implied - args.market_cap) / args.market_cap
    print(f'通过：{args.code}（{market}）{ts:%Y-%m-%d %H:%M:%S} 价 {args.price} '
          f'量 {args.volume:,.0f} 市值 {args.market_cap:,.0f}，价×股本偏差 {dev:.2%}')
    if out.get('preopen_warning'):
        print(f'警告：{out["preopen_warning"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

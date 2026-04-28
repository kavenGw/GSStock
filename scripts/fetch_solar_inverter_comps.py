"""阳光电源同业 comps 数据采集
落地到 scripts/_solar_comps_data.txt 避免管道吞 stdout
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import akshare as ak
import urllib.request
from datetime import datetime

OUT = open(r"D:\Git\stock\scripts\_solar_comps_data.txt", "w", encoding="utf-8")

def log(msg=""):
    print(msg, file=OUT)
    OUT.flush()

PEERS = [
    ("300274", "阳光电源", "sz300274"),
    ("300763", "锦浪科技", "sz300763"),
    ("688390", "固德威",   "sh688390"),
    ("605117", "德业股份", "sh605117"),
    ("300827", "上能电气", "sz300827"),
    ("688032", "禾迈股份", "sh688032"),
    ("002335", "科华数据", "sz002335"),
]

# === 1. 财务摘要（按年度）===
log("=" * 80)
log("PART 1 — 同花顺财务摘要（按年度）")
log("=" * 80)
for code, name, _ in PEERS:
    log(f"\n--- {name} ({code}) ---")
    try:
        df = ak.stock_financial_abstract_ths(symbol=code, indicator="按年度")
        # 仅保留 2018+ 年度
        df["年份"] = df["报告期"].astype(str).str[:4]
        df = df[df["年份"].astype(int) >= 2018]
        log(df.to_string(index=False))
    except Exception as e:
        log(f"ERROR: {type(e).__name__}: {e}")

# === 2. PE-TTM / PB 5y 历史分位（百度估值）===
log("\n" + "=" * 80)
log("PART 2 — 百度估值（PE-TTM / PB 近5年）")
log("=" * 80)
for code, name, _ in PEERS:
    log(f"\n--- {name} ({code}) ---")
    for ind in ["市盈率(TTM)", "市净率"]:
        try:
            df = ak.stock_zh_valuation_baidu(symbol=code, indicator=ind, period="近5年")
            if df is None or df.empty:
                log(f"  {ind}: 空")
                continue
            df["value"] = df["value"].astype(float)
            valid = df[df["value"] > 0]
            if valid.empty:
                log(f"  {ind}: 全部为负或0")
                continue
            cur = valid["value"].iloc[-1]
            mn  = valid["value"].min()
            mx  = valid["value"].max()
            md  = valid["value"].median()
            pct = (valid["value"] <= cur).sum() / len(valid) * 100
            log(f"  {ind}: cur={cur:.2f}  min={mn:.2f}  max={mx:.2f}  median={md:.2f}  pct={pct:.0f}%  n={len(valid)}")
        except Exception as e:
            log(f"  {ind}: ERROR {type(e).__name__}: {e}")

# === 3. 实时价（腾讯 HTTP 批量）===
log("\n" + "=" * 80)
log("PART 3 — 腾讯实时价")
log("=" * 80)
codes = ",".join(t for _, _, t in PEERS)
url = f"http://qt.gtimg.cn/q={codes}"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode("gbk", errors="ignore")
    for line in raw.split("\n"):
        line = line.strip()
        if not line or "=" not in line:
            continue
        # v_sh688032="1~..."
        prefix, payload = line.split("=", 1)
        payload = payload.strip().strip('";')
        parts = payload.split("~")
        if len(parts) < 50:
            continue
        # 索引: 1=name 2=code 3=price 4=close 5=open 6=volume_lots 9=high 10=low ... 39=mcap_yi 45=pb 46=hold_pct
        try:
            sym = parts[2]
            nm = parts[1]
            price = float(parts[3])
            close = float(parts[4])
            chg_pct = (price - close) / close * 100 if close else 0
            mcap = float(parts[45]) if parts[45] else 0   # 总市值（亿）
            float_mcap = float(parts[44]) if parts[44] else 0  # 流通市值（亿）
            pe = float(parts[39]) if parts[39] else 0   # 动态PE
            pb_v = float(parts[46]) if parts[46] else 0
            log(f"  {sym} {nm}: 价格={price} 涨跌={chg_pct:+.2f}% 总市值={mcap:.0f}亿 PE={pe} PB={pb_v}")
        except Exception as e:
            log(f"  parse error: {e}")
except Exception as e:
    log(f"实时价 ERROR: {type(e).__name__}: {e}")

OUT.close()
print("DONE — written to scripts/_solar_comps_data.txt")

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import json
import akshare as ak

out = {}

# 主营构成
try:
    df = ak.stock_zygc_em(symbol='SZ002851')
    latest = df[df['报告日期'] == df['报告日期'].max()]
    out['zygc'] = latest.to_dict(orient='records')
except Exception as e:
    out['zygc_err'] = f'{type(e).__name__}: {e}'

# 多年财务时序
try:
    fa = ak.stock_financial_abstract_ths(symbol='002851', indicator='按年度')
    out['fin_abstract'] = fa.to_dict(orient='records')
except Exception as e:
    out['fin_abstract_err'] = f'{type(e).__name__}: {e}'

# PE 5年分位
try:
    pe = ak.stock_zh_valuation_baidu(symbol='002851', indicator='市盈率(TTM)', period='近5年')
    out['pe5y'] = pe.tail(3).to_dict(orient='records')
    out['pe5y_stats'] = {'min': float(pe['value'].min()), 'max': float(pe['value'].max()),
                         'cur': float(pe['value'].iloc[-1]), 'median': float(pe['value'].median())}
except Exception as e:
    out['pe5y_err'] = f'{type(e).__name__}: {e}'

# PB 5年分位
try:
    pb = ak.stock_zh_valuation_baidu(symbol='002851', indicator='市净率', period='近5年')
    out['pb5y_stats'] = {'min': float(pb['value'].min()), 'max': float(pb['value'].max()),
                         'cur': float(pb['value'].iloc[-1]), 'median': float(pb['value'].median())}
except Exception as e:
    out['pb5y_err'] = f'{type(e).__name__}: {e}'

Path(r'D:\Git\stock\.omc\artifacts\_mgmt_ak.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print('DONE')

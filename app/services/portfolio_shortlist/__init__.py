"""Portfolio shortlist evaluation engine.

把候选股按 (rating + docs 证据 + 技术形态) 打分后取 Top N，
入选后按打分归一化分配主题内 StockWeight。

详见 docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md
"""
# 子模块由调用方按需 import：
#   from app.services.portfolio_shortlist.doc_cache import DocCache
#   from app.services.portfolio_shortlist.scoring import score_stock
#   ...

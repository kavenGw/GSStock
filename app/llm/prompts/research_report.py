"""持仓股票研报分析 Prompt 模板"""

# ── 相关性评估 ──

RESEARCH_RELEVANCE_SYSTEM_PROMPT = (
    "你是证券研报筛选助手。根据搜索结果判断每条内容与指定股票研报的相关性。"
    "返回JSON数组，每个元素包含 index(序号) 和 score(1-5分)。"
)


def build_relevance_prompt(stock_name: str, stock_code: str,
                           results: list[dict]) -> str:
    items = []
    for i, r in enumerate(results):
        items.append(f"{i+1}. 标题: {r['title']}\n   摘要: {r.get('snippet', '无')}")
    items_text = '\n'.join(items)

    return f"""目标股票：{stock_name}（{stock_code}）

以下是搜索结果，请为每条评分：
5=专业研报/评级变动  4=深度分析文章  3=一般分析  2=相关新闻  1=无关内容

{items_text}

返回JSON数组（不要markdown代码块包裹）：
[{{"index": 1, "score": 5}}, {{"index": 2, "score": 3}}, ...]"""


# ── 研报分析 ──

RESEARCH_ANALYSIS_SYSTEM_PROMPT = (
    "你是专业的证券分析师。根据提供的研报和分析师观点，整理关键信息。"
    "用简洁中文输出，不要编造信息。"
)


def build_analysis_prompt(stock_name: str, stock_code: str,
                          materials: list[dict]) -> str:
    parts = []
    for i, m in enumerate(materials):
        content = m.get('content') or m.get('snippet', '')
        parts.append(f"--- 材料{i+1} ---\n标题: {m['title']}\n{content}")
    materials_text = '\n\n'.join(parts)

    return f"""目标股票：{stock_name}（{stock_code}）

以下是最新的研报和分析师观点：

{materials_text}

请整理出以下关键信息（没有的项直接省略，不要编造）：

1. **评级变动**：近期是否有机构上调/下调/维持评级
2. **目标价**：各机构给出的目标价区间
3. **核心逻辑**：看多/看空的主要理由
4. **关键事件**：影响股价的近期事件（财报、产品、政策等）
5. **风险提示**：主要风险因素

直接返回分析文本，不要JSON格式。"""

"""财报对比分析 prompts"""
import json

EARNINGS_COMPARE_SYSTEM_PROMPT = """你是专业的财务分析师。根据提供的公司两期财报数据，进行对比分析。

要求：
1. 自行选择最有价值的指标进行分析（不同行业侧重不同）
2. 指出关键变化和趋势
3. 给出简洁的投资参考观点
4. 200-400字，结构化输出

格式：
**核心指标变化**：（列出3-5个关键指标的同比变化）
**分析**：（解读变化原因和意义）
**关注点**：（投资者应关注的风险或机会）

直接返回分析文本。"""


def build_earnings_compare_prompt(company_name: str, stock_code: str,
                                   report_type: str,
                                   current_data: dict,
                                   previous_data: dict) -> str:
    """构建财报对比 prompt"""
    return (
        f"公司：{company_name}（{stock_code}）\n"
        f"报告类型：{report_type}\n\n"
        f"当期数据：\n{json.dumps(current_data, ensure_ascii=False, indent=2)}\n\n"
        f"上期数据：\n{json.dumps(previous_data, ensure_ascii=False, indent=2)}\n\n"
        f"请进行对比分析。"
    )

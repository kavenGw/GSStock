"""新闻去重判断 prompt"""

DEDUP_SYSTEM_PROMPT = "你是新闻去重判断器。判断两条新闻是否报道同一事件。只回答 yes 或 no。"


MAX_TEXT_LEN = 500


def build_dedup_prompt(text_a: str, text_b: str) -> str:
    a = text_a[:MAX_TEXT_LEN] if len(text_a) > MAX_TEXT_LEN else text_a
    b = text_b[:MAX_TEXT_LEN] if len(text_b) > MAX_TEXT_LEN else text_b
    return f"新闻A: {a}\n新闻B: {b}"

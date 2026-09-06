---
paths:
  - "app/llm/**"
---
# LLM 配置

> **何时读**：改 app/llm/、模型路由、限流/超时、llama-server、日预算

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ZHIPU_API_KEY` | 智谱 GLM（仅免费 glm-4-flash） | 空 |
| `GEMINI_API_KEY` | Gemini，多 key 逗号分隔（FLASH/PREMIUM 主力） | 空 |
| `LLM_DAILY_BUDGET` | 日预算上限（美元） | 无上限 |
| `LLM_REQUEST_TIMEOUT` | 请求超时（秒） | `300` |
| `LLM_RATE_LIMIT_RPM` | 智谱全局限流（RPM） | `10` |
| `LLAMA_SERVER_ENABLED` | 启用本地 llama-server | `false` |
| `LLAMA_SERVER_URL` | llama-server 地址 | `http://127.0.0.1:8080` |
| `LLAMA_MAX_CONTEXT` | 上下文窗口 | `4096` |

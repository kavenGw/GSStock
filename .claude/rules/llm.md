# LLM 配置

> **何时读**：改 app/llm/、调 LLM 模型路由、改限流/超时、配 llama-server、调日预算
> **不必读**：非 LLM 相关

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `ZHIPU_API_KEY` | 智谱 GLM API 密钥（仅免费 glm-4-flash） | 空 |
| `GEMINI_API_KEY` | Google Gemini API 密钥，多个逗号分隔（FLASH/PREMIUM 主力） | 空 |
| `LLM_DAILY_BUDGET` | 日预算上限（美元） | 无上限 |
| `LLM_REQUEST_TIMEOUT` | API 请求超时（秒） | `300` |
| `LLM_RATE_LIMIT_RPM` | 智谱 API 全局限流（RPM） | `10` |
| `LLAMA_SERVER_ENABLED` | 启用本地 llama-server | `false` |
| `LLAMA_SERVER_URL` | llama-server 地址 | `http://127.0.0.1:8080` |
| `LLAMA_MAX_CONTEXT` | llama-server 上下文窗口大小 | `4096` |

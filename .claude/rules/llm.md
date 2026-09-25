---
paths:
  - "app/llm/**"
---
# LLM 配置

> **何时读**：改 app/llm/、模型路由、限流/超时、llama-server、日预算

环境变量清单与默认值见 `.env.sample`。带坑的几项：

- `ZHIPU_API_KEY` 只用免费 `glm-4-flash`，全局限流 `LLM_RATE_LIMIT_RPM`（默认 10）。
- `GEMINI_API_KEY` 多 key 逗号分隔轮换，FLASH/PREMIUM 档主力。
- `LLM_DAILY_BUDGET` 默认无上限；`LLM_REQUEST_TIMEOUT` 默认 300s。
- 本地 `LLAMA_SERVER_ENABLED` 默认关，`LLAMA_MAX_CONTEXT` 默认 4096，超长 prompt 须自己截断。

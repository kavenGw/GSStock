# 启动验证

Windows 使用 `start.bat`，优先选择 `venv\Scripts\python.exe`。Linux 使用 `update_and_run.sh` 更新并启动，或 `./gsstock start` 仅启动。更新流程仍会强制同步 origin/main；Git、依赖或浏览器安装失败立即停止。

两个入口共用 `startup.py`。启动前拒绝占用的 5000 端口；Web 必须返回本次启动的唯一标识，避免把旧服务当作成功。Windows 使用无 reloader 的单进程 Flask；Linux 使用 Gunicorn，完成验证后才写入 PID 文件并返回成功。

进程内逐项输出 PASS / WAIT / SKIP / FAIL：

- Chromium 实际启动并关闭；只读模式跳过。
- 主库和 private 库执行查询，并核对 ORM 表的字段存在。
- 六个市场的状态缓存完成初始化。
- Windows OCR 模型实际加载；Linux 跳过。
- 所有 Blueprint 注册、策略发现、通知事件订阅。
- 已配置 LLM 客户端初始化、行情源配置检查；不验证远端认证、不执行推理、不发送测试通知。
- 调度器启动并核对固定任务及每个已启用策略的任务；赛事监控恢复失败也终止启动。

调度器在暂停状态完成检查，成功后恢复原有新闻轮询和业务任务。验证本身不主动执行这些任务；正常运行仍有原来的轮询、补发和赛事恢复行为。可选 Torch 保留原有可选语义。

`STARTUP_TIMEOUT` 默认 120 秒，`LLAMA_STARTUP_TIMEOUT` 默认 300 秒，可在环境或 `.env` 中设置。明确的初始化错误或子进程退出立即失败；仍在初始化则等待到上限。失败返回非零退出码并清理本次创建的进程，已存在的 llama-server 不会被停止。

启用 llama-server 后检查 `/health` 返回 `status=ok`。Windows 默认本地 8080 地址无人监听时直接启动 `llama-server`，模型路径通过 `LLAMA_MODEL_PATH` 设置，默认保持原批处理的路径。其他地址及 Linux 使用已部署的服务并验证就绪。`llama-server.bat` 仍可手动使用，其无限重启逻辑不参与主启动流程。

模块明细与异常栈在 `logs/startup.log`；Gunicorn 错误在 `logs/error.log`；本次拉起的 llama-server 输出在 `logs/llama-startup.log`。本机制只验证启动阶段，不提供持续业务健康监控。

回归测试：`python -m pytest tests/services/test_startup.py tests/test_gunicorn_conf.py -q`。测试使用临时 HTTP 服务及独立子进程，不启动实际业务或操作生产数据库。

# 新闻轮询分时段动态间隔

## 背景

当前新闻轮询使用固定间隔（`NEWS_INTERVAL_MINUTES` 默认3分钟），公司新闻使用内嵌节流（`COMPANY_NEWS_INTERVAL_MINUTES` 默认30分钟）。需求是交易活跃时段（9:00-14:59）提高轮询频率，非活跃时段降低频率。

## 设计

### 环境变量

移除 `NEWS_INTERVAL_MINUTES` 和 `COMPANY_NEWS_INTERVAL_MINUTES`，新增：

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `NEWS_ACTIVE_INTERVAL_MINUTES` | 活跃时段（9:00-14:59）新闻轮询间隔 | `10` |
| `NEWS_INACTIVE_INTERVAL_MINUTES` | 非活跃时段新闻轮询间隔 | `30` |
| `COMPANY_NEWS_ACTIVE_INTERVAL_MINUTES` | 活跃时段公司新闻轮询间隔 | `10` |
| `COMPANY_NEWS_INACTIVE_INTERVAL_MINUTES` | 非活跃时段公司新闻轮询间隔 | `30` |

时间窗口固定为 9:00-14:59（即 hour 9-14），15:00 起进入非活跃时段。值必须是 60 的因子（1/2/3/4/5/6/10/12/15/20/30/60），否则 cron `*/N` 在跨小时时间隔不均匀。

### 调度器变更（engine.py）

用 CronTrigger 替代 IntervalTrigger，每类轮询注册两个 job：

**通用新闻**：
- `news_poll_active`：CronTrigger `*/N 9-14 * * *`（N = NEWS_ACTIVE_INTERVAL_MINUTES）
- `news_poll_inactive`：CronTrigger `*/N 0-8,15-23 * * *`（N = NEWS_INACTIVE_INTERVAL_MINUTES）

**公司新闻**：
- `company_news_active`：CronTrigger `*/N 9-14 * * *`
- `company_news_inactive`：CronTrigger `*/N 0-8,15-23 * * *`

两组 job 调用相同的处理函数，hour 范围无重叠，不会双触发。

**Job 参数**：
- `next_run_time=datetime.now()`：启动时立即触发首次轮询
- `coalesce=True`：合并错过的执行
- `misfire_grace_time=30`：30秒内的 misfire 仍执行
- `max_instances=1`：防止上次未完成时重复启动（公司新闻爬虫可能耗时较长）

### 公司新闻独立调度

- 从 `news_service.py` 的 `poll_news()` 中**完整移除**公司新闻内嵌节流：
  - 模块级变量 `_last_company_news_time`
  - `global _last_company_news_time` 声明
  - 时间检查和 `_executor.submit()` 调用
- `engine.py` 新增 `_poll_company_news()` 方法，模式与 `_poll_news()` 一致（`app_context` + 异常处理）

### 配置文件变更（news_config.py）

- 移除：`NEWS_INTERVAL_MINUTES`、`COMPANY_NEWS_INTERVAL_MINUTES`
- 新增：4个分时段间隔变量

### 文档同步

更新 CLAUDE.md、README.md、.env.sample 中的环境变量说明。

## 涉及文件

| 文件 | 变更 |
|-----|------|
| `app/config/news_config.py` | 替换环境变量 |
| `app/scheduler/engine.py` | CronTrigger 双 job + 公司新闻独立调度 |
| `app/services/news_service.py` | 移除公司新闻内嵌节流（含模块级变量清理） |
| `.env.sample` | 更新配置项 |
| `CLAUDE.md` | 更新环境变量文档 |
| `README.md` | 更新环境变量文档 |

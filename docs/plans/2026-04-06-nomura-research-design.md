# 野村研报爬虫设计

## 概述

新增野村证券官网 (nomuraconnects.com) 作为独立研报数据源，独立推送到 `news_research` 频道。

## 数据源

- 列表页：`https://www.nomuraconnects.com/economics/` + `/central-banks/`
- 文章页：`https://www.nomuraconnects.com/focused-thinking-posts/{slug}/`
- 无需登录，服务端渲染HTML，crawl4ai可抓取
- 无RSS/API

## 架构

最小改动，新增独立服务+策略：

```
app/services/nomura_research_service.py   # 新增
app/strategies/nomura_research/__init__.py # 新增
app/llm/prompts/nomura_research.py        # 新增
```

## 流程

1. 爬取 economics + central-banks 列表页，解析文章链接和标题
2. 关键词过滤：Asia/China/Japan/CNY/亚洲/中国 等
3. MD5 hash 去重（3天缓存窗口）
4. crawl4ai 抓取匹配文章全文
5. GLM Flash 整理关键观点
6. 推送到 news_research：`📊 野村研报精选 (日期)`

## 调度

- Cron: `10 20 * * 1-5`（工作日20:10，错开华尔街见闻10分钟）

## 推送测试

两个服务各加 `test_push()` 方法，命令行可调用：

```bash
SCHEDULER_ENABLED=0 python -c "from app import create_app; app=create_app(); ..."
```

## 环境变量

- `NOMURA_RESEARCH_ENABLED`（默认 true）

## 不改动

- wallstreet_news_service.py 保持不变
- 现有策略调度不变

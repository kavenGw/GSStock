# Slack 推送仅限兴趣+公司新闻 - 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将新闻 Slack 推送从「所有快讯入库即推」改为「仅推送兴趣新闻和公司新闻」

**Architecture:** 删除 `news_service.py` 中的全量推送逻辑，在 `interest_pipeline.py` 处理完关键词匹配后推送兴趣新闻，在 `company_news_service.py` 保存完公司新闻后推送公司新闻。

**Tech Stack:** Flask, NotificationService.send_slack()

---

### Task 1: 删除 news_service.py 中的全量推送

**Files:**
- Modify: `app/services/news_service.py`

**Step 1: 删除 poll_news() 中的 Slack 推送调用**

删除第 144 行：
```python
_executor.submit(NewsService._notify_slack, [n.content for n in new_items])
```

**Step 2: 删除 `_notify_slack` 方法**

删除第 149-174 行的 `_notify_slack` 静态方法。

**Step 3: 删除 `_ai_select_key_news` 方法**

删除第 176-207 行的 `_ai_select_key_news` 静态方法。

**Step 4: 验证**

启动应用确认无导入错误：`python -c "from app.services.news_service import NewsService; print('OK')"`

**Step 5: Commit**

```bash
git add app/services/news_service.py
git commit -m "refactor: 移除新闻全量Slack推送"
```

---

### Task 2: 在 interest_pipeline.py 中添加兴趣新闻推送

**Files:**
- Modify: `app/services/interest_pipeline.py`

**Step 1: 在 process_new_items() 的 db.session.commit() 之后添加推送逻辑**

在第 31 行 `db.session.commit()` 之后，第 33 行衍生搜索之前，添加：

```python
            # Slack 推送兴趣新闻
            interest_items = [n for n in items if n.is_interest]
            if interest_items:
                InterestPipeline._notify_interest_slack(interest_items)
```

**Step 2: 添加 `_notify_interest_slack` 静态方法**

在类末尾添加：

```python
    @staticmethod
    def _notify_interest_slack(items: list[NewsItem]):
        from app.services.notification import NotificationService
        try:
            for n in items:
                NotificationService.send_slack(f"📰 {n.content}")
        except Exception as e:
            logger.error(f'[兴趣] Slack通知失败: {e}')
```

注意：`process_new_items` 已在 `app.app_context()` 内运行，不需要额外创建 context。

**Step 3: 验证**

`python -c "from app.services.interest_pipeline import InterestPipeline; print('OK')"`

**Step 4: Commit**

```bash
git add app/services/interest_pipeline.py
git commit -m "feat: 兴趣新闻匹配后推送Slack"
```

---

### Task 3: 在 company_news_service.py 中添加公司新闻推送

**Files:**
- Modify: `app/services/company_news_service.py`

**Step 1: 修改 `_save_results` 方法，收集新增条目并推送**

当前 `_save_results` 只做存储。需要：
1. 收集新增的 `NewsItem` 对象（跳过 existing 的）
2. commit 成功后推送

修改 `_save_results` 方法，在 `db.session.add(news)` 后收集 news 对象，commit 成功后推送：

```python
    @staticmethod
    def _save_results(results: list[dict]):
        from app.llm.router import llm_router

        provider = llm_router.route('news_classify')
        new_items = []

        for item in results:
            source_id = hashlib.md5(item['url'].encode()).hexdigest()[:16]
            source_name = item['source_name']

            existing = NewsItem.query.filter_by(
                source_id=source_id, source_name=source_name
            ).first()
            if existing:
                continue

            content = item['content']
            if provider and item['source_name'] != 'eastmoney_stock':
                try:
                    content = provider.chat([
                        {'role': 'system', 'content': SUMMARY_PROMPT},
                        {'role': 'user', 'content': item['content']},
                    ], temperature=0.1, max_tokens=200).strip()
                except Exception as e:
                    logger.error(f'[公司新闻] AI摘要失败: {e}')

            news = NewsItem(
                source_id=source_id,
                source_name=source_name,
                content=content,
                display_time=datetime.now(),
                score=1,
                is_interest=True,
                matched_keywords=item['company'],
            )
            db.session.add(news)
            new_items.append((item['company'], content))

        try:
            db.session.commit()
            # Slack 推送新增公司新闻
            if new_items:
                CompanyNewsService._notify_company_slack(new_items)
        except Exception as e:
            db.session.rollback()
            logger.error(f'[公司新闻] 保存失败: {e}')
```

**Step 2: 添加 `_notify_company_slack` 静态方法**

```python
    @staticmethod
    def _notify_company_slack(items: list[tuple[str, str]]):
        from app.services.notification import NotificationService
        try:
            for company, content in items:
                NotificationService.send_slack(f"🏢 [{company}] {content}")
        except Exception as e:
            logger.error(f'[公司新闻] Slack通知失败: {e}')
```

**Step 3: 验证**

`python -c "from app.services.company_news_service import CompanyNewsService; print('OK')"`

**Step 4: Commit**

```bash
git add app/services/company_news_service.py
git commit -m "feat: 公司新闻爬取后推送Slack"
```

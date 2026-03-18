# 新闻推送去重设计

## 问题

新闻系统从4个源（华尔街见闻、财联社、SmolAI、36氪）并行获取新闻，现有去重仅按 `(source_id, source_name)` 判断，无法处理跨源重复。同一事件从不同源获取后，兴趣新闻和公司新闻渠道各自推送，导致用户收到多条内容相似的 Slack 通知。

## 方案

在推送 Slack 前增加文本相似度去重层，30分钟窗口内同一事件只推送一条（保留内容最详细的）。

## 组件设计

### NewsDeduplicator (`app/services/news_dedup.py`)

单例类，维护内存中的已推送缓冲区。`threading.Lock` 保护并发访问。

```python
_pushed_buffer: list[tuple[datetime, str]]  # (推送时间, 新闻内容)
_lock: threading.Lock
```

核心方法：

```python
def filter_duplicates(self, items: list[T], content_key: Callable[[T], str]) -> list[T]:
    """
    content_key: 内容提取函数
      - NewsItem: lambda item: item.content
      - tuple: lambda item: item[1]
    """
```

去重流程：
1. 清理缓冲区中超过30分钟的旧记录
2. 批内贪心分组（遍历列表，将每条与已有组的代表项比较，相似则归入该组），每组保留 `len(content)` 最长的一条
3. 与已推送缓冲区比较，过滤掉相似的
4. 过滤完成后立即将通过的内容加入缓冲区（即使后续 send_slack 失败也不影响，防重优先）

文本预处理：`re.sub(r'[\s\W]+', '', text)` 去除标点、空白和 emoji。

缓冲区纯内存，进程重启自动清空。

日志：每次过滤记录 `[去重] 输入 N 条，过滤 M 条重复，推送 K 条`。

## 集成点

两处推送方法在发送前调用 `NewsDeduplicator.filter_duplicates()` 过滤：

1. **兴趣新闻** — `interest_pipeline.py` 的 `_notify_interest_slack(items)`
   - `deduplicator.filter_duplicates(items, content_key=lambda n: n.content)`
2. **公司新闻** — `company_news_service.py` 的 `_notify_company_slack(items)`
   - `deduplicator.filter_duplicates(items, content_key=lambda t: t[1])`

两个渠道共享同一个 `NewsDeduplicator` 实例，跨渠道重复也能检测。

## 涉及文件

- 新增：`app/services/news_dedup.py`
- 修改：`app/services/interest_pipeline.py`、`app/services/company_news_service.py`

## 技术细节

- 零外部依赖，使用 Python 标准库 `difflib.SequenceMatcher`
- 相似度阈值：0.4（上线后通过日志观察误判情况再调整）
- 时间窗口：30分钟
- 同事件多条新闻：保留内容最长的一条
- 当前规模下（4源，每轮约20-50条），性能开销可忽略

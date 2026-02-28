# 新闻看板兴趣模块设计

## 概述

完善新闻看板的兴趣模块，实现：自定义关键词匹配、GLM 智能分类打分、按重要性分级的衍生搜索、多新闻源整合、AI 关键词推荐。

## 架构：同步流水线 + 后台衍生

```
多源拉取 → 合并去重入库 → GLM批量分类打分 → 关键词匹配 → 标记兴趣
                                                              ↓ importance>=4
                                                   后台线程: crawl4ai衍生搜索 → GLM整理专题
```

## 1. 数据模型

### 新增: InterestKeyword（用户兴趣关键词）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| keyword | TEXT NOT NULL | 关键词 |
| source | TEXT DEFAULT 'user' | 来源：'user' / 'ai' |
| is_active | BOOLEAN DEFAULT 1 | 是否启用 |
| created_at | DATETIME | 创建时间 |

### 新增: NewsDerivation（衍生新闻）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| news_item_id | INTEGER FK | 关联 news_item.id |
| search_query | TEXT | crawl4ai 搜索查询词 |
| sources | JSON | 抓取的来源URL列表 |
| summary | TEXT | GLM 整理的专题报告 |
| importance | INTEGER | 重要性评分(1-5) |
| created_at | DATETIME | 创建时间 |

### 修改: NewsItem 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| importance | INTEGER DEFAULT 0 | GLM评分(1-5)，0=未评分 |
| is_interest | BOOLEAN DEFAULT 0 | 是否命中用户关键词 |
| matched_keywords | TEXT | 命中的关键词，逗号分隔 |
| source_name | TEXT DEFAULT 'wallstreetcn' | 新闻来源标识 |

### 删除

- NewsBriefing 模型（遗留废弃）

## 2. 新闻源架构

### 统一接口

```python
class NewsSourceBase:
    name: str
    def fetch_latest() -> list[dict]
        # 返回: [{content, source_id, display_time, source_name}]
```

### 预设新闻源

| 源 | 类型 | 说明 |
|---|------|------|
| 华尔街见闻 | API | 现有逻辑迁移 |
| smol.ai | RSS | `https://news.smol.ai/rss.xml`，AI/科技 |
| 财联社 | API/爬虫 | 中文财经快讯 |
| 36kr | RSS | 科技商业 |

### 数据流

- 各源 ThreadPoolExecutor 并行获取
- 统一格式合并，`(source_id, source_name)` 联合唯一约束去重

## 3. GLM 分类打分 + 关键词匹配

### 流水线

```
新条目(批量) → Step1: GLM Flash批量分类打分 → Step2: 关键词匹配 → Step3: 标记兴趣
```

**Step 1**：一次调用处理最多20条，GLM Flash 返回 JSON：
```json
[{"index": 0, "importance": 3, "keywords": ["英伟达", "AI芯片"]}, ...]
```

**Step 2**：GLM 提取的 keywords 与 InterestKeyword 表模糊匹配（完全匹配优先，包含匹配兜底）

**Step 3**：命中 → `is_interest=True`，`matched_keywords` 记录命中词

### AI 关键词推荐

每天一次，GLM 分析最近7天兴趣新闻，推荐新关键词 → 存入 `InterestKeyword(source='ai', is_active=False)` → 用户确认后启用

## 4. 衍生搜索机制

### 分级策略

| 评分 | 搜索深度 |
|------|---------|
| 1-3 | 仅标记兴趣，不衍生 |
| 4 | 轻量：crawl4ai 抓 1-2 链接，GLM 生成扩展摘要（100-200字） |
| 5 | 深度：crawl4ai 抓 3-5 篇，GLM 生成结构化专题（背景/影响/展望，300-500字） |

### 执行流程

1. GLM Flash 生成搜索关键词（中英文各一组）
2. crawl4ai 异步抓取搜索结果页 + 正文
3. GLM 整合原始新闻 + 衍生内容
4. 存入 NewsDerivation 表

### 限制

- ThreadPoolExecutor 后台执行，不阻塞 poll
- 单次最多抓 5 个 URL，并发上限 3
- 每 URL 超时 30 秒，总超时 2 分钟/任务
- 每次 poll 最多触发 2 个衍生任务

## 5. 前端交互

### 兴趣 Tab

- 重要性星级显示（★）
- 命中关键词小标签
- 衍生内容折叠展开（importance=5 默认展开，4 折叠）
- 来源标签（华尔街/SmolAI/财联社/36kr）

### 关键词管理弹窗

- ⚙️ 入口打开管理界面
- 用户关键词：标签样式 + ✕ 删除
- AI 推荐：灰色标签，✓ 接受 / ✕ 拒绝
- 添加输入框即时生效

## 6. LLM 成本控制与错误处理

### 调用点

| 调用点 | 模型 | 频率 |
|--------|------|------|
| 批量分类打分 | Flash | 每次 poll |
| 衍生关键词生成 | Flash | 仅高分 |
| 衍生内容整合 | Flash(4分)/Premium(5分) | 仅高分 |
| AI 关键词推荐 | Flash | 每天一次 |

### 降级策略

- GLM 分类失败 → 跳过，importance=0
- 关键词匹配失败 → 跳过，保留在"全部"Tab
- crawl4ai 超时 → 仅用原始新闻让 GLM 生成简短摘要
- GLM 衍生失败 → 存 crawl4ai 原始 markdown
- 所有 LLM 失败 → 新闻正常入库，兴趣功能静默降级

核心原则：LLM 和爬虫是增强层，任何失败不影响基础新闻功能。

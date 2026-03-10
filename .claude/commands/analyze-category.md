---
description: 分析指定板块的所有股票，设计二级分类并添加投资建议
allowed-tools: Bash, Read, Grep, Glob, Write, Edit, Agent, WebSearch, WebFetch
---

# 板块分析与二级分类

对指定板块下的股票进行产业链分析，设计二级分类，并为每只股票撰写投资建议。

## 输入

`$ARGUMENTS` 为板块名称（如 "CPO"、"半导体"）。如果为空，询问用户。

## 执行步骤

### 1. 查询板块现状

```python
from app import create_app, db
from app.models.category import Category, StockCategory
from app.models.stock import Stock

app = create_app()
with app.app_context():
    cat = Category.query.filter_by(name='板块名').first()
    # 获取所有子分类（如已有）
    children = Category.query.filter_by(parent_id=cat.id).all()
    # 获取板块下所有股票（包括子分类中的）
    cat_ids = [cat.id] + [c.id for c in children]
    stock_cats = StockCategory.query.filter(StockCategory.category_id.in_(cat_ids)).all()
    for sc in stock_cats:
        s = db.session.get(Stock, sc.stock_code)
        # 输出: 代码、名称、当前分类、投资建议
```

### 2. 研究每只股票

使用 Agent (general-purpose) 并行研究所有股票，对每只获取：
- 主营业务与核心产品/技术
- 在该板块产业链中的位置（上游/中游/下游/配套）
- 市场地位与竞争优势
- 近期业绩与重大事件

### 3. 设计二级分类

基于产业链分析结果：
- 按产业链环节划分子分类（如：光芯片/光模块、光调制器、MEMS光开关、PCB基板）
- 每个子分类应有明确的产业链定位
- 将每只股票归入最匹配的子分类

### 4. 撰写投资建议

为每只股票写一段投资建议（不超过500字），包含：
- 产业链地位一句话定位
- 关键业绩数据或催化剂
- 风险提示
- 操作建议（趋势跟踪/中线布局/长线价值等）

### 5. 展示方案并确认

以表格形式展示：
- 子分类结构（树形）
- 每只股票的分类归属
- 每只股票的投资建议

**等待用户确认后再执行数据库变更。**

### 6. 执行变更

用户确认后，通过 Python 脚本执行：

```python
with app.app_context():
    # 1. 创建子分类 (parent_id=板块id)
    # 2. 更新 StockCategory.category_id 到对应子分类
    # 3. 更新 Stock.investment_advice
    db.session.commit()
```

注意事项：
- 编码问题：脚本开头加 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')`
- 抑制启动日志：`2>/dev/null`
- 如果已有子分类，询问用户是否重新划分或增量调整

## 规则

- 如果板块已有子分类，先展示现有结构，询问是重新划分还是调整
- 投资建议控制在500字以内，简洁有力
- 必须等用户确认后才执行数据库变更
- 研究股票信息时使用并行 Agent 提升效率

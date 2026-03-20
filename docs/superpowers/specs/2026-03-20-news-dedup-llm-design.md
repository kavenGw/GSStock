# LLM 辅助批内新闻去重

## 背景

当前跨源去重有三个通道（文本相似度、指纹匹配、包含度检测），但对于同一事件不同源的报道，存在漏检：
- 长短差异大的文章文本相似度低于 0.4 阈值
- 通用公司名（xAI、OpenAI 等）不在 Stock/CompanyKeyword 表中，指纹通道无法提取
- 用词差异（"派遣" vs "派往"）导致包含度覆盖率不足

## 方案

在 `filter_duplicates()` 的**批内分组去重**阶段增加第四通道 `llm`，对规则未命中但"可疑"的文章对调用 LLM Flash 判断是否同一事件。

## 流程

```
批内 items
  ↓
1. 现有规则分组（text/fingerprint/containment），缓存相似度分数
  ↓
2. 未合并组的代表两两检查"可疑对"预筛选（复用缓存分数）
  ↓  命中
3. 释放锁 → 调 LLM Flash 判断是否同一事件 → 重新获取锁
  ↓  是
4. 合并到同组，保留最长文本
```

跨历史去重不变，仍用纯规则。

## 可疑对预筛选

两条件任一满足即为可疑对。检查对象是**未被合并的组代表**（单独成组的条目 + 多条目组的第一条），已归入某组的非代表成员不参与。

### 规则软匹配（复用第一轮缓存的分数）
- 文本相似度在 0.2-0.4 之间（低于正式阈值但有信号）
- 或指纹重叠特征数 = 1（低于正式要求的 ≥2）

实现：拆出 `_text_similarity_score()` 返回 float，`_fingerprint_overlap_count()` 返回 int，第一轮规则匹配时缓存分数，第二轮预筛选复用。

### 通用关键词重叠
用正则从文本中提取通用实体：
- **英文词**：≥3 字符的连续英文字母（`[A-Za-z]{3,}`），排除停用词：CEO/CFO/CTO/COO/IPO/ETF/GDP/API/APP/THE/AND/FOR 等
- **中文机构名**：`([\u4e00-\u9fa5]{2,6})(公司|集团|银行|证券|科技|基金|保险|控股|汽车|电子|医药|能源)`，排除代词/泛指开头（该/上市/多家/一家/这家/那家）

两条新闻有 ≥2 个共同关键词即为可疑对。

## LLM 调用

- **模型**：Flash，在 `TASK_LAYER_MAP` 注册 `'news_dedup': LLMLayer.FLASH`
- **参数**：`temperature=0.1, max_tokens=10`
- **Prompt**：新建 `app/llm/prompts/news_dedup.py`

```
System: 你是新闻去重判断器。判断两条新闻是否报道同一事件。只回答 yes 或 no。
User: 新闻A: {text_a}\n新闻B: {text_b}
```

- **响应解析**：`response.strip().lower().startswith('yes')` 判定为重复
- **容错**：LLM 调用失败或响应无法解析时降级为放行（不过滤），不阻塞推送流程
- **无调用上限**：批内可疑对数量自然有限，不设人为限制

## 并发策略

当前 `filter_duplicates` 整体在 `self._lock` 内。LLM 网络调用不能在锁内执行（会阻塞其他线程）。

处理方式：
1. 锁内完成规则分组 + 收集可疑对列表
2. **释放锁**
3. 锁外并行调用 LLM 判断所有可疑对
4. **重新获取锁**，执行 LLM 判定的合并 + 跨历史去重 + 写入 buffer

## 结果处理

- LLM 判定为同一事件 → 合并到同组，保留最长文本（与现有通道一致）
- 单层合并，不处理传递性（A↔B、B↔C 不会级联合并 A↔C）
- 日志记录 `llm` 通道命中数，纳入现有统计

## 不变的部分

- 跨历史去重仍用纯规则
- 批内现有三通道（text/fingerprint/containment）逻辑不变
- `PushedRecord` 结构不变
- 去重窗口、阈值等配置不变

## 涉及文件

- `app/services/news_dedup.py` — 主要修改：增加可疑对预筛选 + LLM 调用逻辑，拆分锁段
- `app/llm/prompts/news_dedup.py` — 新建：去重判断 prompt
- `app/llm/router.py` — 在 `TASK_LAYER_MAP` 注册 `'news_dedup': LLMLayer.FLASH`

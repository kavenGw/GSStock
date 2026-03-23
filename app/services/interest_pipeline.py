"""新闻兴趣流水线：分类打分 → 关键词匹配 → 衍生搜索"""
import json
import logging
import re

from app import db
from app.models.news import NewsItem, InterestKeyword, CompanyKeyword, IdentifiedCompany

logger = logging.getLogger(__name__)


class InterestPipeline:

    @staticmethod
    def process_new_items(item_ids: list[int], app=None):
        """处理新入库的新闻条目（在后台线程执行）"""
        if app is None:
            from flask import current_app
            app = current_app._get_current_object()

        with app.app_context():
            items = NewsItem.query.filter(NewsItem.id.in_(item_ids)).all()
            if not items:
                return

            # Step 1: GLM 批量分类打分
            classified = InterestPipeline._classify_items(items)

            # Step 2: 关键词匹配
            InterestPipeline._match_keywords(items, classified)

            db.session.commit()

            # Slack 推送兴趣新闻
            interest_items = [n for n in items if n.is_interest]
            if interest_items:
                InterestPipeline._notify_interest_slack(interest_items)


    CLASSIFY_BATCH_SIZE = 10

    @staticmethod
    def _is_local_provider(provider) -> bool:
        """检测 provider 是否为本地 llama-server（含 FallbackProvider 包装）"""
        name = getattr(provider, 'name', '')
        if name == 'llama-server':
            return True
        primary = getattr(provider, 'primary', None)
        return getattr(primary, 'name', '') == 'llama-server'

    @staticmethod
    def _classify_items(items: list[NewsItem]) -> list[dict]:
        """GLM 批量分类打分（本地模型仅处理1条，其余走云端）"""
        from app.llm.router import llm_router
        from app.llm.prompts.news_classify import CLASSIFY_SYSTEM_PROMPT, build_classify_prompt

        provider = llm_router.route('news_classify')
        if not provider:
            return []

        is_local = InterestPipeline._is_local_provider(provider)

        # 构建分批计划: (provider, start, end, max_tokens)
        batches = []
        if is_local and len(items) > 1 and hasattr(provider, 'fallback'):
            # 本地模型串行慢，只让1条走本地，其余直接走云端
            batches.append((provider, 0, 1, 500))
            cloud = provider.fallback
            for s in range(1, len(items), InterestPipeline.CLASSIFY_BATCH_SIZE):
                batches.append((cloud, s, min(s + InterestPipeline.CLASSIFY_BATCH_SIZE, len(items)), 4000))
            logger.info(f'[分类] {len(items)}条新闻: 1条→本地, {len(items)-1}条→云端')
        else:
            bs = 1 if is_local else InterestPipeline.CLASSIFY_BATCH_SIZE
            mt = 500 if is_local else 4000
            for s in range(0, len(items), bs):
                batches.append((provider, s, min(s + bs, len(items)), mt))

        all_results = []
        for prov, batch_start, batch_end, max_tok in batches:
            batch = items[batch_start:batch_end]
            batch_data = [{'content': n.content} for n in batch]
            try:
                response = prov.chat([
                    {'role': 'system', 'content': CLASSIFY_SYSTEM_PROMPT},
                    {'role': 'user', 'content': build_classify_prompt(batch_data)},
                ], temperature=0.1, max_tokens=max_tok)

                results = InterestPipeline._parse_classify_response(response)
                results = [r for r in results if isinstance(r, dict)]
                for r in results:
                    local_idx = r.get('index', -1)
                    if 0 <= local_idx < len(batch):
                        global_idx = batch_start + local_idx
                        r['index'] = global_idx
                        items[global_idx].importance = r.get('importance', 0)
                        if r.get('is_earnings') and r.get('stock_code'):
                            items[global_idx].category = 'earnings'
                all_results.extend(results)
            except Exception as e:
                logger.error(f'GLM分类打分失败(batch {batch_start}~{batch_end - 1}): {e}')

        return all_results

    @staticmethod
    def _parse_classify_response(response: str) -> list[dict]:
        """解析 GLM 分类响应，支持截断 JSON 容错恢复"""
        text = response.strip()
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            text = m.group(1).strip()
        if not text.startswith('['):
            arr_match = re.search(r'\[[\s\S]*\]', text)
            if arr_match:
                text = arr_match.group(0)

        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return [result]
            return result
        except json.JSONDecodeError:
            pass

        # 截断容错：找最后一个完整对象，截断后闭合数组，恢复已解析的条目
        last_brace = text.rfind('}')
        if last_brace > 0:
            repaired = text[:last_brace + 1].rstrip(',') + ']'
            try:
                result = json.loads(repaired)
                logger.warning(f'GLM分类JSON截断容错，恢复 {len(result)} 条')
                return result if isinstance(result, list) else [result]
            except json.JSONDecodeError:
                pass

        # 逐个提取 JSON 对象（处理 LLM 返回 "[0]\n{...}" 等非标准格式）
        objects = re.findall(r'\{[^{}]*\}', text)
        if objects:
            results = []
            for obj_str in objects:
                try:
                    results.append(json.loads(obj_str))
                except json.JSONDecodeError:
                    continue
            if results:
                logger.warning(f'GLM分类JSON格式异常，逐对象提取恢复 {len(results)} 条')
                return results

        logger.error(f'GLM分类打分JSON解析失败, 响应长度={len(response)}, 末尾: ...{response[-200:]}')
        return []

    @staticmethod
    def _build_stock_tag_index():
        """构建股票标签反向索引 {tag_lower: [stock_code, ...]}"""
        from app.models.stock import Stock
        stock_tag_index = {}
        all_stocks = Stock.query.filter(Stock.tags.isnot(None), Stock.tags != '').all()
        for stock in all_stocks:
            for tag in stock.tags.split(','):
                tag = tag.strip().lower()
                if tag and len(tag) >= 2:
                    if tag not in stock_tag_index:
                        stock_tag_index[tag] = []
                    stock_tag_index[tag].append(stock.stock_code)
        return stock_tag_index

    @staticmethod
    def _match_stocks_for_item(item: NewsItem, stock_tag_index: dict):
        """对单条新闻做股票标签匹配"""
        content_lower = item.content.lower()
        matched_codes = set()
        for tag, codes in stock_tag_index.items():
            if tag in content_lower:
                matched_codes.update(codes)
        if matched_codes:
            item.matched_stocks = ','.join(sorted(matched_codes))

    @staticmethod
    def _match_keywords(items: list[NewsItem], classified: list[dict]):
        """将 GLM 提取的关键词与用户兴趣关键词+公司名匹配，同时做股票标签匹配"""
        user_keywords = InterestKeyword.query.filter_by(is_active=True).all()
        company_keywords = CompanyKeyword.query.filter_by(is_active=True).all()

        kw_set = {kw.keyword.lower() for kw in user_keywords}
        kw_set.update(c.name.lower() for c in company_keywords)

        stock_tag_index = InterestPipeline._build_stock_tag_index()

        classified_indices = set()
        for r in classified:
            idx = r.get('index', -1)
            if idx < 0 or idx >= len(items):
                continue
            classified_indices.add(idx)
            item = items[idx]
            extracted = r.get('keywords', [])

            # 兴趣关键词匹配
            matched = []
            if kw_set:
                for ext_kw in extracted:
                    ext_lower = ext_kw.lower()
                    for user_kw in kw_set:
                        if user_kw in ext_lower or ext_lower in user_kw:
                            matched.append(user_kw)
                            break

                if not matched:
                    content_lower = item.content.lower()
                    for user_kw in kw_set:
                        if user_kw in content_lower:
                            matched.append(user_kw)

            if matched:
                item.is_interest = True
                item.matched_keywords = ','.join(set(matched))

            # 股票标签匹配
            if stock_tag_index:
                InterestPipeline._match_stocks_for_item(item, stock_tag_index)

        # 对未被 classified 覆盖的新闻也做标签匹配
        if stock_tag_index:
            for i, item in enumerate(items):
                if i not in classified_indices:
                    InterestPipeline._match_stocks_for_item(item, stock_tag_index)

    @staticmethod
    def recommend_keywords(app=None):
        """AI 推荐新关键词（每天调用一次）"""
        if app is None:
            from flask import current_app
            app = current_app._get_current_object()

        with app.app_context():
            from app.llm.router import llm_router
            from app.llm.prompts.news_classify import RECOMMEND_SYSTEM_PROMPT, build_recommend_prompt
            from datetime import datetime, timedelta

            week_ago = datetime.now() - timedelta(days=7)
            recent = NewsItem.query.filter(
                NewsItem.is_interest == True,
                NewsItem.created_at >= week_ago
            ).order_by(NewsItem.created_at.desc()).limit(50).all()

            if len(recent) < 5:
                return

            existing = InterestKeyword.query.filter_by(is_active=True).all()
            existing_kws = [kw.keyword for kw in existing]

            provider = llm_router.route('news_recommend')
            if not provider:
                return

            is_local = InterestPipeline._is_local_provider(provider)
            contents = [n.content for n in recent]
            if is_local:
                contents = contents[:10]
            try:
                response = provider.chat([
                    {'role': 'system', 'content': RECOMMEND_SYSTEM_PROMPT},
                    {'role': 'user', 'content': build_recommend_prompt(contents, existing_kws)},
                ], temperature=0.3, max_tokens=200)

                text = response.strip()
                m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
                if m:
                    text = m.group(1).strip()
                suggestions = json.loads(text)
                for kw in suggestions:
                    if isinstance(kw, str) and kw not in existing_kws:
                        db.session.add(InterestKeyword(
                            keyword=kw, source='ai', is_active=False
                        ))
                db.session.commit()
                logger.info(f'[兴趣] AI推荐 {len(suggestions)} 个关键词')
            except Exception as e:
                logger.error(f'AI关键词推荐失败: {e}')

    # 触发公司识别的关键词
    _UNNAMED_COMPANY_HINTS = ('这家公司', '该公司', '这家企业', '该企业', '此公司')

    @staticmethod
    def _identify_company(content: str) -> str | None:
        """用 Gemini 识别推送中描述的未具名公司，Gemini 不可用时降级到 GLM"""
        if not any(hint in content for hint in InterestPipeline._UNNAMED_COMPANY_HINTS):
            return None
        try:
            from app.llm.prompts.company_identify import (
                COMPANY_IDENTIFY_SYSTEM_PROMPT, build_company_identify_prompt,
            )
            messages = [
                {'role': 'system', 'content': COMPANY_IDENTIFY_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_company_identify_prompt(content)},
            ]

            from app.llm.providers.gemini import GeminiFlashProvider, GEMINI_API_KEY
            if GEMINI_API_KEY:
                provider = GeminiFlashProvider()
            else:
                from app.llm.router import llm_router
                provider = llm_router.route('company_identify')
            if not provider:
                return None

            result = provider.chat(messages, temperature=0.1, max_tokens=500).strip()
            if result and result != '无法确定':
                return result
        except Exception as e:
            logger.error(f'[兴趣] 公司识别失败: {e}')
        return None

    @staticmethod
    def _notify_interest_slack(items: list[NewsItem]):
        from app.services.notification import NotificationService
        from app.services.news_dedup import news_deduplicator
        from app.services.company_news_service import _format_table_content
        try:
            items = news_deduplicator.filter_duplicates(items, content_key=lambda n: n.content)
            if not items:
                return

            # 预加载关联股票名称
            all_codes = set()
            for n in items:
                if n.matched_stocks:
                    all_codes.update(n.matched_stocks.split(','))

            stock_name_map = {}
            if all_codes:
                from app.models.stock import Stock
                stocks = Stock.query.filter(Stock.stock_code.in_(all_codes)).all()
                stock_name_map = {s.stock_code: s.stock_name for s in stocks}

            for n in items:
                tag = f" [{n.matched_keywords}]" if n.matched_keywords else ""
                formatted = _format_table_content(n.content)
                if formatted != n.content:
                    title_line = formatted.split('\n', 1)[0]
                    table_body = '\n'.join(formatted.split('\n')[1:])
                    msg = f"📰{tag} {title_line}\n```\n{table_body}\n```"
                else:
                    msg = f"📰{tag} {n.content}"

                if n.matched_stocks:
                    codes = n.matched_stocks.split(',')
                    stock_labels = [f"{c}{stock_name_map.get(c, '')}" for c in codes]
                    msg += f"\n→ 关联: {', '.join(stock_labels)}"

                # GLM 识别未具名公司
                identified = InterestPipeline._identify_company(n.content)
                if identified:
                    msg += f"\n🔍 AI识别: {identified}"
                    InterestPipeline._save_identified_companies(n.content, identified)

                NotificationService.send_slack(msg)
        except Exception as e:
            logger.error(f'[兴趣] Slack通知失败: {e}')

    @staticmethod
    def _save_identified_companies(news_content: str, raw_result: str):
        """解析AI识别结果并保存到数据库"""
        # 格式：公司名称(股票代码) - 理由  或  公司名称（股票代码） - 理由
        pattern = re.compile(r'(.+?)[（(]([^)）]+)[)）]\s*[-—]\s*(.+)')
        try:
            for line in raw_result.strip().splitlines():
                line = line.strip()
                if not line or '无法确定' in line:
                    continue
                m = pattern.match(line)
                if m:
                    name, code, reason = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                else:
                    name, code, reason = line, '', ''
                record = IdentifiedCompany(
                    company_name=name, stock_code=code,
                    news_content=news_content, reason=reason,
                    raw_result=raw_result,
                )
                db.session.add(record)
            db.session.commit()
        except Exception as e:
            logger.error(f'[兴趣] 保存识别公司失败: {e}')

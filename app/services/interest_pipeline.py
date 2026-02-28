"""新闻兴趣流水线：分类打分 → 关键词匹配 → 衍生搜索"""
import json
import logging
import re

from app import db
from app.models.news import NewsItem, InterestKeyword, CompanyKeyword

logger = logging.getLogger(__name__)


class InterestPipeline:

    @staticmethod
    def process_new_items(item_ids: list[int]):
        """处理新入库的新闻条目（在后台线程执行）"""
        from app import create_app
        app = create_app()

        with app.app_context():
            items = NewsItem.query.filter(NewsItem.id.in_(item_ids)).all()
            if not items:
                return

            # Step 1: GLM 批量分类打分
            classified = InterestPipeline._classify_items(items)

            # Step 2: 关键词匹配
            InterestPipeline._match_keywords(items, classified)

            db.session.commit()

            # Step 3: 高分兴趣条目触发衍生搜索（需 NEWS_DERIVATION_ENABLED=true）
            import os
            if os.getenv('NEWS_DERIVATION_ENABLED', 'false').lower() == 'true':
                from app.services.derivation_service import DerivationService
                interest_items = [n for n in items if n.is_interest and n.importance >= 4]
                DerivationService.process_batch(interest_items[:2])

    @staticmethod
    def _classify_items(items: list[NewsItem]) -> list[dict]:
        """GLM 批量分类打分"""
        from app.llm.router import llm_router
        from app.llm.prompts.news_classify import CLASSIFY_SYSTEM_PROMPT, build_classify_prompt

        provider = llm_router.route('news_classify')
        if not provider:
            return []

        items_data = [{'content': n.content} for n in items]
        try:
            response = provider.chat([
                {'role': 'system', 'content': CLASSIFY_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_classify_prompt(items_data)},
            ], temperature=0.1, max_tokens=2000)

            text = response.strip()
            # GLM 有时返回 ```json ... ``` 包裹的内容
            m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if m:
                text = m.group(1).strip()
            # 尝试提取JSON数组
            if not text.startswith('['):
                arr_match = re.search(r'\[[\s\S]*\]', text)
                if arr_match:
                    text = arr_match.group(0)
            results = json.loads(text)
            for r in results:
                idx = r.get('index', -1)
                if 0 <= idx < len(items):
                    items[idx].importance = r.get('importance', 0)
            return results
        except json.JSONDecodeError:
            logger.error(f'GLM分类打分JSON解析失败, 原始返回: {response[:200]}')
            return []
        except Exception as e:
            logger.error(f'GLM分类打分失败: {e}')
            return []

    @staticmethod
    def _match_keywords(items: list[NewsItem], classified: list[dict]):
        """将 GLM 提取的关键词与用户兴趣关键词+公司名匹配"""
        user_keywords = InterestKeyword.query.filter_by(is_active=True).all()
        company_keywords = CompanyKeyword.query.filter_by(is_active=True).all()

        kw_set = {kw.keyword.lower() for kw in user_keywords}
        kw_set.update(c.name.lower() for c in company_keywords)

        if not kw_set:
            return

        for r in classified:
            idx = r.get('index', -1)
            if idx < 0 or idx >= len(items):
                continue
            item = items[idx]
            extracted = r.get('keywords', [])

            matched = []
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

    @staticmethod
    def recommend_keywords():
        """AI 推荐新关键词（每天调用一次）"""
        from app import create_app
        app = create_app()

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

            contents = [n.content for n in recent]
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

"""GitHub Trending 监控服务 — 爬取热门项目并推送新上榜的"""
import json
import logging
import os
import re

import requests

from app.config.github_trending import (
    GITHUB_TRENDING_ENABLED, GITHUB_TRENDING_TOP_N, GITHUB_TRENDING_URL,
)

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
PUSHED_FILE = os.path.join(DATA_DIR, 'github_trending_pushed.json')
FETCH_TIMEOUT = 15


class GitHubTrendingService:

    @staticmethod
    def _fetch_html() -> str:
        """请求 GitHub Trending 页面"""
        try:
            resp = requests.get(
                GITHUB_TRENDING_URL,
                headers={'User-Agent': 'Mozilla/5.0 (compatible; stock-bot/1.0)'},
                timeout=FETCH_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.warning(f'[GitHub Trending] 页面获取失败: {e}')
            return ''

    @staticmethod
    def _parse_html(html: str) -> list[dict]:
        """解析 Trending 页面，提取 Top N 项目信息

        GitHub Trending 页面结构：
        - 每个项目在 <article class="Box-row"> 内
        - repo 链接在 h2 > a[href] 中，href 格式 /owner/repo
        - 描述在 <p class="..."> 中
        - star 总数和今日增量在 <span> 中
        """
        repos = []
        article_pattern = re.compile(
            r'<article\s+class="Box-row">(.*?)</article>',
            re.DOTALL,
        )
        for match in article_pattern.finditer(html):
            block = match.group(1)

            # repo 全名（从 h2 标签内的链接提取，避免匹配到 sponsor 链接）
            h2_match = re.search(r'<h2[^>]*>(.*?)</h2>', block, re.DOTALL)
            if not h2_match:
                continue
            name_match = re.search(r'href="(/[^"]+)"', h2_match.group(1))
            if not name_match:
                continue
            full_name = name_match.group(1).strip('/')
            if '/' not in full_name:
                continue

            # 描述
            desc_match = re.search(r'<p\s+class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            description = ''
            if desc_match:
                description = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip()

            # star 总数
            stars = ''
            star_links = re.findall(r'href="/[^"]+/stargazers"[^>]*>(.*?)</a>', block, re.DOTALL)
            if star_links:
                stars = re.sub(r'<[^>]+>', '', star_links[0]).strip().replace(',', ',')

            # 今日新增 star
            today_stars = ''
            today_match = re.search(r'(\d[\d,]*)\s+stars?\s+today', block, re.IGNORECASE)
            if today_match:
                today_stars = today_match.group(1)

            repos.append({
                'full_name': full_name,
                'description': description,
                'stars': stars,
                'today_stars': today_stars,
                'url': f'https://github.com/{full_name}',
            })

            if len(repos) >= GITHUB_TRENDING_TOP_N:
                break

        return repos

    @staticmethod
    def _get_pushed() -> set[str]:
        """读取已推送的 repo 全名集合"""
        try:
            if os.path.exists(PUSHED_FILE):
                with open(PUSHED_FILE, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
        except Exception as e:
            logger.warning(f'[GitHub Trending] 读取已推送记录失败: {e}')
        return set()

    @staticmethod
    def _mark_pushed(names: list[str]):
        """追加已推送的 repo 全名"""
        existing = GitHubTrendingService._get_pushed()
        existing.update(names)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(PUSHED_FILE, 'w', encoding='utf-8') as f:
                json.dump(list(existing), f, ensure_ascii=False)
        except Exception as e:
            logger.warning(f'[GitHub Trending] 写入已推送记录失败: {e}')

    @staticmethod
    def _summarize(repo_name: str, description: str) -> str:
        """GLM Flash 生成中文摘要"""
        try:
            from app.llm.router import llm_router
            from app.llm.prompts.github_trending_summary import (
                GITHUB_TRENDING_SUMMARY_SYSTEM_PROMPT,
                build_github_trending_summary_prompt,
            )

            provider = llm_router.route('github_trending_summary')
            if not provider:
                return ''

            prompt = build_github_trending_summary_prompt(repo_name, description)
            summary = provider.chat(
                [
                    {'role': 'system', 'content': GITHUB_TRENDING_SUMMARY_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=150,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f'[GitHub Trending] LLM 摘要失败 {repo_name}: {e}')
            return ''

    @staticmethod
    def fetch_trending() -> list[dict]:
        """主入口：获取新上榜的 trending 项目（含摘要）

        Returns:
            新项目列表，每项包含 full_name, description, stars, today_stars, url, summary
            首次运行返回空列表（只记录，不推送）
        """
        if not GITHUB_TRENDING_ENABLED:
            return []

        html = GitHubTrendingService._fetch_html()
        if not html:
            return []

        repos = GitHubTrendingService._parse_html(html)
        if not repos:
            logger.warning('[GitHub Trending] 未解析到任何项目')
            return []

        pushed = GitHubTrendingService._get_pushed()

        # 首次运行：记录当前列表，不推送
        if not pushed:
            logger.info(f'[GitHub Trending] 首次运行，记录 {len(repos)} 个项目')
            GitHubTrendingService._mark_pushed([r['full_name'] for r in repos])
            return []

        new_repos = [r for r in repos if r['full_name'] not in pushed]
        if not new_repos:
            logger.info('[GitHub Trending] 无新上榜项目')
            return []

        logger.info(f'[GitHub Trending] 发现 {len(new_repos)} 个新上榜项目')

        # LLM 摘要
        for repo in new_repos:
            summary = GitHubTrendingService._summarize(repo['full_name'], repo['description'])
            repo['summary'] = summary or repo['description']

        # 标记已推送
        GitHubTrendingService._mark_pushed([r['full_name'] for r in new_repos])

        return new_repos

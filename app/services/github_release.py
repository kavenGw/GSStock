"""GitHub Release 通用监控服务 - 从 GitHub Releases 获取多仓库版本信息"""
import json
import logging
import os
import ssl
from urllib.request import urlopen, Request

import certifi

from app.config.github_releases import GITHUB_RELEASE_REPOS

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')


class GitHubReleaseService:

    @staticmethod
    def get_new_releases(repo: str, key: str) -> list[dict]:
        """获取指定仓库自上次推送以来的新版本"""
        releases = GitHubReleaseService._fetch_releases_from_github(repo)
        if not releases:
            return []

        last_version = GitHubReleaseService._get_last_pushed_version(key)
        return GitHubReleaseService._filter_new_releases(releases, last_version)

    @staticmethod
    def _fetch_releases_from_github(repo: str) -> list[dict]:
        """从 GitHub API 获取最近 10 个 release"""
        url = f'https://api.github.com/repos/{repo}/releases?per_page=10'
        try:
            req = Request(
                url,
                headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'stock-briefing-bot'},
            )
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=15, context=ssl_ctx) as resp:
                if resp.status != 200:
                    logger.warning(f'[GitHub Release] {repo} API 返回 {resp.status}')
                    return []
                data = json.loads(resp.read().decode())

            return [
                {
                    'version': r.get('tag_name', ''),
                    'published_at': (r.get('published_at') or '')[:10],
                    'body': r.get('body') or '',
                    'url': r.get('html_url') or '',
                }
                for r in data
                if not r.get('draft') and not r.get('prerelease')
            ]
        except Exception as e:
            logger.warning(f'[GitHub Release] {repo} API 调用失败: {e}')
            return []

    @staticmethod
    def _get_last_pushed_version(key: str) -> str | None:
        """读取指定仓库上次推送的版本号"""
        version_file = os.path.join(DATA_DIR, f'github_release_{key}_last_version.txt')
        try:
            if os.path.exists(version_file):
                with open(version_file, 'r') as f:
                    return f.read().strip() or None
        except OSError as e:
            logger.warning(f'[GitHub Release] 读取 {key} 版本标记失败: {e}')
        return None

    @staticmethod
    def mark_pushed_version(key: str, version: str) -> None:
        """写入指定仓库已推送版本号"""
        version_file = os.path.join(DATA_DIR, f'github_release_{key}_last_version.txt')
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(version_file, 'w') as f:
                f.write(version)
        except OSError as e:
            logger.warning(f'[GitHub Release] 写入 {key} 版本标记失败: {e}')

    @staticmethod
    def _filter_new_releases(releases: list[dict], last_version: str | None) -> list[dict]:
        """筛选出比 last_version 更新的版本；首次运行只取最新 1 个"""
        if not releases:
            return []

        if last_version is None:
            return releases[:1]

        new_releases = []
        for r in releases:
            if r['version'] == last_version:
                break
            new_releases.append(r)
        return new_releases

    @staticmethod
    def get_all_updates() -> list[dict]:
        """遍历静态配置 + 本地已装插件对应仓库（按 repo 去重，静态优先），返回每个仓库的更新"""
        from app.services.plugin_discovery import discover_plugin_repos

        seen_repos = {cfg['repo'].lower() for cfg in GITHUB_RELEASE_REPOS}
        merged = list(GITHUB_RELEASE_REPOS)
        for cfg in discover_plugin_repos():
            if cfg['repo'].lower() not in seen_repos:
                merged.append(cfg)
                seen_repos.add(cfg['repo'].lower())

        results = []
        for repo_cfg in merged:
            releases = GitHubReleaseService.get_new_releases(repo_cfg['repo'], repo_cfg['key'])
            results.append({'config': repo_cfg, 'releases': releases})
        return results

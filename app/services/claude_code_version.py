"""Claude Code 版本更新服务 - 从 GitHub Releases 获取版本信息"""
import json
import logging
import os
import ssl
from urllib.request import urlopen, Request

import certifi

logger = logging.getLogger(__name__)

GITHUB_RELEASES_URL = 'https://api.github.com/repos/anthropics/claude-code/releases'
VERSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'claude_code_last_version.txt')


class ClaudeCodeVersionService:

    @staticmethod
    def get_new_releases() -> list[dict]:
        """获取自上次推送以来的新版本"""
        releases = ClaudeCodeVersionService._fetch_releases_from_github()
        if not releases:
            return []

        last_version = ClaudeCodeVersionService._get_last_pushed_version()
        return ClaudeCodeVersionService._filter_new_releases(releases, last_version)

    @staticmethod
    def _fetch_releases_from_github() -> list[dict]:
        """从 GitHub API 获取最近 10 个 release"""
        try:
            req = Request(
                f'{GITHUB_RELEASES_URL}?per_page=10',
                headers={'Accept': 'application/vnd.github.v3+json', 'User-Agent': 'stock-briefing-bot'},
            )
            ssl_ctx = ssl.create_default_context(cafile=certifi.where())
            with urlopen(req, timeout=15, context=ssl_ctx) as resp:
                if resp.status != 200:
                    logger.warning(f'[Claude Code 版本] GitHub API 返回 {resp.status}')
                    return []
                data = json.loads(resp.read().decode())

            return [
                {
                    'version': r.get('tag_name', ''),
                    'published_at': (r.get('published_at') or '')[:10],
                    'body': r.get('body') or '',
                }
                for r in data
                if not r.get('draft') and not r.get('prerelease')
            ]
        except Exception as e:
            logger.warning(f'[Claude Code 版本] GitHub API 调用失败: {e}')
            return []

    @staticmethod
    def _get_last_pushed_version() -> str | None:
        """读取上次推送的版本号"""
        try:
            if os.path.exists(VERSION_FILE):
                with open(VERSION_FILE, 'r') as f:
                    return f.read().strip() or None
        except OSError as e:
            logger.warning(f'[Claude Code 版本] 读取版本标记失败: {e}')
        return None

    @staticmethod
    def mark_pushed_version(version: str) -> None:
        """写入已推送版本号"""
        try:
            os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
            with open(VERSION_FILE, 'w') as f:
                f.write(version)
        except OSError as e:
            logger.warning(f'[Claude Code 版本] 写入版本标记失败: {e}')

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

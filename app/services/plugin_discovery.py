"""扫描本地 Claude Code 插件目录，动态发现 marketplace 对应的 GitHub 仓库"""
import json
import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _default_plugins_dir() -> Path:
    return Path(os.environ.get('CLAUDE_PLUGINS_DIR') or (Path.home() / '.claude' / 'plugins'))


def _extract_github_repo(source: dict) -> str | None:
    """从 known_marketplaces.json 的 source 字段提取 'owner/repo'，非 github 源返回 None"""
    if source.get('source') == 'github' and source.get('repo'):
        return source['repo']
    url = source.get('url') or ''
    m = re.search(r'github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$', url)
    return f'{m.group(1)}/{m.group(2)}' if m else None


def discover_plugin_repos() -> list[dict]:
    """返回本地已装插件对应的 GitHub 仓库配置，目录缺失/非 github 源自动跳过"""
    base = _default_plugins_dir()
    installed_fp = base / 'installed_plugins.json'
    markets_fp = base / 'known_marketplaces.json'

    if not installed_fp.exists() or not markets_fp.exists():
        return []

    try:
        installed = json.loads(installed_fp.read_text(encoding='utf-8')).get('plugins', {})
        markets = json.loads(markets_fp.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        logger.warning(f'[PluginDiscovery] 读取插件目录失败: {e}')
        return []

    active_markets = {k.split('@', 1)[1] for k in installed.keys() if '@' in k}

    results = []
    for mk_name in sorted(active_markets):
        mk_cfg = markets.get(mk_name)
        if not mk_cfg:
            continue
        repo = _extract_github_repo(mk_cfg.get('source') or {})
        if not repo:
            continue
        results.append({
            'key': f'marketplace_{mk_name}',
            'repo': repo,
            'name': mk_name,
            'emoji': '📦',
        })
    return results

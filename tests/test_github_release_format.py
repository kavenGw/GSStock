"""GitHub Release Slack 推送格式优化测试"""


def test_prompt_requests_json_with_features_and_fixes():
    from app.llm.prompts.github_release_update import build_github_release_update_prompt

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Added X env var. Fixed SIGINT handling.',
    }]
    prompt = build_github_release_update_prompt('Claude Code', releases)

    assert 'JSON' in prompt
    assert 'features' in prompt
    assert 'fixes' in prompt
    assert 'versions' in prompt
    assert 'v2.1.132' in prompt
    assert '2026-05-06' in prompt


def test_format_release_block_full():
    from app.services.notification import NotificationService

    version_data = {
        'version': 'v2.1.132',
        'date': '2026-05-06',
        'features': [
            '新增 `CLAUDE_CODE_SESSION_ID` 环境变量',
            '粘贴图片时显示 "Pasting..." 提示',
        ],
        'fixes': [
            'SIGINT 信号未正确处理',
            '`--permission-mode` 标志被忽略',
        ],
    }
    text = NotificationService._format_release_block('Claude Code', '🤖', version_data)

    assert text.startswith('🤖 *Claude Code v2.1.132* (2026-05-06)')
    assert '✨ *新功能*' in text
    assert '• 新增 `CLAUDE_CODE_SESSION_ID` 环境变量' in text
    assert '🐛 *修复*' in text
    assert '• SIGINT 信号未正确处理' in text


def test_format_release_block_skips_empty_features():
    from app.services.notification import NotificationService

    version_data = {
        'version': 'v1.0.0',
        'date': '2026-05-01',
        'features': [],
        'fixes': ['修复 A'],
    }
    text = NotificationService._format_release_block('Tool', '🛠', version_data)

    assert '✨ *新功能*' not in text
    assert '🐛 *修复*' in text
    assert '• 修复 A' in text


def test_format_release_block_skips_empty_fixes():
    from app.services.notification import NotificationService

    version_data = {
        'version': 'v1.0.0',
        'date': '2026-05-01',
        'features': ['新增 A'],
        'fixes': [],
    }
    text = NotificationService._format_release_block('Tool', '🛠', version_data)

    assert '✨ *新功能*' in text
    assert '• 新增 A' in text
    assert '🐛 *修复*' not in text


import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def fake_repo_cfg():
    return {
        'key': 'claude_code',
        'repo': 'anthropics/claude-code',
        'name': 'Claude Code',
        'emoji': '🤖',
    }


def _patch_get_all_updates(repo_cfg, releases):
    """Helper: 替换 GitHubReleaseService.get_all_updates 的返回"""
    return patch(
        'app.services.github_release.GitHubReleaseService.get_all_updates',
        return_value=[{'config': repo_cfg, 'releases': releases}],
    )


def _patch_llm(json_str_or_exception):
    """Helper: mock llm_router.route(...).chat(...) 的返回或抛异常"""
    provider = MagicMock()
    if isinstance(json_str_or_exception, Exception):
        provider.chat.side_effect = json_str_or_exception
    else:
        provider.chat.return_value = json_str_or_exception

    router_mock = MagicMock()
    router_mock.route.return_value = provider
    return patch('app.llm.router.llm_router', router_mock)


def test_format_uses_json_for_categorized_output(fake_repo_cfg):
    from app.services.notification import NotificationService

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Added X. Fixed Y.',
        'url': 'https://github.com/anthropics/claude-code/releases/tag/v2.1.132',
    }]
    llm_json = (
        '{"versions": [{"version": "v2.1.132", "date": "2026-05-06", '
        '"features": ["新增 `X` 环境变量"], "fixes": ["修复 Y 问题"]}]}'
    )

    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm(llm_json):
        texts, pushed = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    assert '🤖 *Claude Code v2.1.132* (2026-05-06)' in texts[0]
    assert '✨ *新功能*' in texts[0]
    assert '• 新增 `X` 环境变量' in texts[0]
    assert '🐛 *修复*' in texts[0]
    assert '• 修复 Y 问题' in texts[0]
    assert 'https://github.com/anthropics/claude-code/releases/tag/v2.1.132' in texts[0]
    assert pushed == [('claude_code', 'v2.1.132')]


def test_format_falls_back_when_llm_returns_non_json(fake_repo_cfg, caplog):
    from app.services.notification import NotificationService

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Some changelog body content here',
        'url': 'https://github.com/x/y/releases/tag/v2.1.132',
    }]
    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm('not valid json at all'):
        texts, _ = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    # 降级路径：含原 changelog 内容
    assert 'Some changelog body content here' in texts[0]
    assert '🤖 Claude Code 更新' in texts[0]
    assert 'https://github.com/x/y/releases/tag/v2.1.132' in texts[0]


def test_format_falls_back_when_all_categories_empty(fake_repo_cfg):
    from app.services.notification import NotificationService

    releases = [{
        'version': 'v2.1.132',
        'published_at': '2026-05-06',
        'body': 'Internal refactor only',
        'url': 'https://github.com/x/y/releases/tag/v2.1.132',
    }]
    llm_json = (
        '{"versions": [{"version": "v2.1.132", "date": "2026-05-06", '
        '"features": [], "fixes": []}]}'
    )
    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm(llm_json):
        texts, _ = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    # 走降级：含原 body
    assert 'Internal refactor only' in texts[0]


def test_format_handles_multi_versions(fake_repo_cfg):
    from app.services.notification import NotificationService

    releases = [
        {
            'version': 'v2.1.132',
            'published_at': '2026-05-06',
            'body': 'Added X.',
            'url': 'https://github.com/x/y/releases/tag/v2.1.132',
        },
        {
            'version': 'v2.1.131',
            'published_at': '2026-05-05',
            'body': 'Fixed Z.',
            'url': 'https://github.com/x/y/releases/tag/v2.1.131',
        },
    ]
    llm_json = (
        '{"versions": ['
        '{"version": "v2.1.132", "date": "2026-05-06", "features": ["新增 X"], "fixes": []},'
        '{"version": "v2.1.131", "date": "2026-05-05", "features": [], "fixes": ["修复 Z"]}'
        ']}'
    )
    with _patch_get_all_updates(fake_repo_cfg, releases), _patch_llm(llm_json):
        texts, pushed = NotificationService.format_github_release_updates()

    assert len(texts) == 1
    assert '🤖 *Claude Code v2.1.132*' in texts[0]
    assert '🤖 *Claude Code v2.1.131*' in texts[0]
    # 链接只出现一次（用最新版本）
    assert texts[0].count('🔗') == 1
    assert 'releases/tag/v2.1.132' in texts[0]
    # pushed 取最新（releases[0]）
    assert pushed == [('claude_code', 'v2.1.132')]

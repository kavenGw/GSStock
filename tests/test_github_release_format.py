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

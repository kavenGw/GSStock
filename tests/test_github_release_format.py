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

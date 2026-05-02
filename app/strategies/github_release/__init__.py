"""GitHub Release 独立监控策略 - 每 6 小时检查一次新版本"""
import logging
import os
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class GitHubReleaseStrategy(Strategy):
    name = "github_release"
    description = "GitHub Release 版本监控"
    schedule = "0 */6 * * *"
    needs_llm = True
    enabled = os.environ.get('GITHUB_RELEASE_ENABLED', 'true').lower() == 'true'

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService
        from app.services.github_release import GitHubReleaseService
        from app.config.notification_config import CHANNEL_AI_TOOL

        release_texts, release_pushed_versions = NotificationService.format_github_release_updates()

        if not release_texts:
            logger.info('[GitHub Release] 无新版本')
            return []

        msg = '\n\n'.join(release_texts)
        if NotificationService.send_slack(msg, CHANNEL_AI_TOOL):
            logger.info(f'[GitHub Release] 推送成功: {len(release_texts)} 个仓库')
            for key, version in release_pushed_versions:
                GitHubReleaseService.mark_pushed_version(key, version)
        else:
            logger.warning('[GitHub Release] 推送失败')

        return []

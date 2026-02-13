"""
消息推送服务 - Slack Webhook + SMTP 邮件
"""
import json
import logging
import smtplib
import ssl
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.request import urlopen, Request

from app.config.notification_config import (
    SLACK_WEBHOOK_URL, SLACK_ENABLED,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL_TO, EMAIL_ENABLED
)

logger = logging.getLogger(__name__)


class NotificationService:
    """消息推送服务"""

    @staticmethod
    def get_status() -> dict:
        """获取推送渠道状态"""
        return {
            'slack': SLACK_ENABLED,
            'email': EMAIL_ENABLED,
        }

    @staticmethod
    def send_slack(message: str) -> bool:
        """推送到 Slack（Incoming Webhook）"""
        if not SLACK_ENABLED:
            logger.warning('[Notification] Slack 未配置')
            return False

        try:
            payload = json.dumps({'text': message}).encode('utf-8')
            req = Request(SLACK_WEBHOOK_URL, data=payload, headers={'Content-Type': 'application/json'})
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f'[Notification] Slack 推送失败: {e}')
            return False

    @staticmethod
    def send_email(subject: str, html_body: str) -> bool:
        """推送邮件（SMTP/SSL）"""
        if not EMAIL_ENABLED:
            logger.warning('[Notification] 邮件未配置')
            return False

        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = SMTP_USER
            msg['To'] = NOTIFY_EMAIL_TO
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=10) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, NOTIFY_EMAIL_TO, msg.as_string())
            return True
        except Exception as e:
            logger.error(f'[Notification] 邮件推送失败: {e}')
            return False

    @staticmethod
    def send_all(subject: str, text_content: str, html_content: str) -> dict:
        """同时推送到所有已配置渠道"""
        results = {}
        if SLACK_ENABLED:
            results['slack'] = NotificationService.send_slack(text_content)
        if EMAIL_ENABLED:
            results['email'] = NotificationService.send_email(subject, html_content)
        return results

    @staticmethod
    def format_briefing_summary() -> dict:
        """生成每日简报摘要（持仓/收益/异常）"""
        from app.services.position import PositionService

        today = date.today()
        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return {'text': '暂无持仓数据', 'html': '<p>暂无持仓数据</p>'}

        positions = PositionService.get_snapshot(latest_date)
        if not positions:
            return {'text': '暂无持仓数据', 'html': '<p>暂无持仓数据</p>'}

        total_market_value = 0
        total_cost = 0
        up_count = 0
        down_count = 0
        items = []

        for p in positions:
            mv = p.current_price * p.quantity
            cost = p.total_amount
            profit = mv - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0

            total_market_value += mv
            total_cost += cost
            if profit > 0:
                up_count += 1
            elif profit < 0:
                down_count += 1

            items.append({
                'code': p.stock_code,
                'name': p.stock_name,
                'price': p.current_price,
                'profit': profit,
                'profit_pct': profit_pct,
            })

        total_profit = total_market_value - total_cost
        total_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

        sign = '+' if total_profit >= 0 else ''

        text = f"持仓概览 ({latest_date})\n"
        text += f"总市值: ¥{total_market_value:,.0f} | 浮盈: {sign}¥{total_profit:,.0f} ({sign}{total_pct:.1f}%)\n"
        text += f"持仓: {len(positions)}只 | 盈利: {up_count} | 亏损: {down_count}\n"

        html = f"<h3>持仓概览 ({latest_date})</h3>"
        html += f"<p>总市值: ¥{total_market_value:,.0f} | 浮盈: {sign}¥{total_profit:,.0f} ({sign}{total_pct:.1f}%)</p>"
        html += f"<p>持仓: {len(positions)}只 | 盈利: {up_count} | 亏损: {down_count}</p>"

        # 盈亏 Top3
        sorted_items = sorted(items, key=lambda x: x['profit_pct'], reverse=True)
        if sorted_items:
            text += "\n盈利 Top3:\n"
            html += "<h4>盈利 Top3</h4><ul>"
            for item in sorted_items[:3]:
                s = '+' if item['profit_pct'] >= 0 else ''
                text += f"  {item['name']}({item['code']}): {s}{item['profit_pct']:.1f}%\n"
                html += f"<li>{item['name']}({item['code']}): {s}{item['profit_pct']:.1f}%</li>"
            html += "</ul>"

            text += "\n亏损 Top3:\n"
            html += "<h4>亏损 Top3</h4><ul>"
            for item in sorted_items[-3:]:
                s = '+' if item['profit_pct'] >= 0 else ''
                text += f"  {item['name']}({item['code']}): {s}{item['profit_pct']:.1f}%\n"
                html += f"<li>{item['name']}({item['code']}): {s}{item['profit_pct']:.1f}%</li>"
            html += "</ul>"

        return {'text': text, 'html': html}

    @staticmethod
    def format_alert_signals() -> dict:
        """生成预警信号摘要"""
        from app.services.signal_cache import SignalCacheService
        from app.services.position import PositionService
        from app.models.stock import Stock
        from app.utils.market_identifier import MarketIdentifier

        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return {'text': '', 'html': ''}

        positions = PositionService.get_snapshot(latest_date)
        a_share_codes = [p.stock_code for p in positions if MarketIdentifier.is_a_share(p.stock_code)]

        if not a_share_codes:
            return {'text': '', 'html': ''}

        name_map = {}
        stocks = Stock.query.filter(Stock.stock_code.in_(a_share_codes)).all()
        for s in stocks:
            name_map[s.stock_code] = s.stock_name
        for p in positions:
            if p.stock_code not in name_map:
                name_map[p.stock_code] = p.stock_name

        signals = SignalCacheService.get_cached_signals_with_names(a_share_codes, name_map)

        buy_signals = signals.get('buy_signals', [])
        sell_signals = signals.get('sell_signals', [])

        if not buy_signals and not sell_signals:
            return {'text': '', 'html': ''}

        text = "预警信号\n"
        html = "<h3>预警信号</h3>"

        if sell_signals:
            text += "\n卖出信号:\n"
            html += "<h4 style='color:#dc2626'>卖出信号</h4><ul>"
            for sig in sell_signals[:10]:
                line = f"{sig.get('stock_name', '')}({sig.get('stock_code', '')}) - {sig.get('name', '')}"
                text += f"  {line}\n"
                html += f"<li>{line}</li>"
            html += "</ul>"

        if buy_signals:
            text += "\n买入信号:\n"
            html += "<h4 style='color:#16a34a'>买入信号</h4><ul>"
            for sig in buy_signals[:10]:
                line = f"{sig.get('stock_name', '')}({sig.get('stock_code', '')}) - {sig.get('name', '')}"
                text += f"  {line}\n"
                html += f"<li>{line}</li>"
            html += "</ul>"

        return {'text': text, 'html': html}

    @staticmethod
    def format_ai_report(analyses: list) -> dict:
        """格式化AI分析报告"""
        if not analyses:
            return {'text': '', 'html': ''}

        text = "AI分析摘要\n"
        html = "<h3>AI分析摘要</h3><ul>"

        for a in analyses:
            code = a.get('stock_code', '')
            name = a.get('stock_name', '')
            result = a.get('result', {})
            signal = result.get('signal', 'HOLD')
            score = result.get('score', '-')
            conclusion = result.get('conclusion', '')

            line = f"{name}({code}): {signal}({score}分) - {conclusion}"
            text += f"  {line}\n"
            html += f"<li><strong>{name}({code})</strong>: {signal}({score}分) - {conclusion}</li>"

        html += "</ul>"
        return {'text': text, 'html': html}

    @staticmethod
    def push_daily_report(include_ai: bool = False) -> dict:
        """一键推送每日报告（简报+预警+AI分析）"""
        today = date.today()
        subject = f'每日股票分析报告 - {today}'

        briefing = NotificationService.format_briefing_summary()
        alerts = NotificationService.format_alert_signals()

        text_parts = [briefing['text']]
        html_parts = [
            f"<h2>每日股票分析报告 - {today}</h2>",
            briefing['html'],
        ]

        if alerts['text']:
            text_parts.append(alerts['text'])
            html_parts.append(alerts['html'])

        if include_ai:
            try:
                from app.services.ai_analyzer import AIAnalyzerService, AI_ENABLED
                if AI_ENABLED:
                    ai_service = AIAnalyzerService()
                    from app.services.position import PositionService
                    latest_date = PositionService.get_latest_date()
                    if latest_date:
                        positions = PositionService.get_snapshot(latest_date)
                        stock_list = [{'code': p.stock_code, 'name': p.stock_name} for p in positions]
                        analyses = ai_service.analyze_batch(stock_list)
                        ai_report = NotificationService.format_ai_report(analyses)
                        if ai_report['text']:
                            text_parts.append(ai_report['text'])
                            html_parts.append(ai_report['html'])
            except Exception as e:
                logger.warning(f'[Notification] AI分析报告生成失败: {e}')

        full_text = '\n---\n'.join(text_parts)
        full_html = '<hr>'.join(html_parts)

        results = NotificationService.send_all(subject, full_text, full_html)
        results['content_preview'] = full_text[:500]
        return results

"""2026 FIFA 世界杯推送配置（临时赛事，结束后整文件删除）"""
import os

WORLDCUP_ENABLED = os.getenv('WORLDCUP_ENABLED', 'true').lower() == 'true'
ESPORTS_WORLDCUP_MONITOR_INTERVAL = int(os.getenv('ESPORTS_WORLDCUP_MONITOR_INTERVAL', '5'))
WORLDCUP_MAX_DURATION_HOURS = 3  # 90'+伤停+中场+加时/点球

ESPN_SOCCER_WC_URL = 'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard'

# ESPN displayName(英) → 中文。未命中回退显示英文原名。
WORLDCUP_TEAM_NAMES = {
    'Argentina': '阿根廷', 'France': '法国', 'Brazil': '巴西', 'England': '英格兰',
    'Spain': '西班牙', 'Portugal': '葡萄牙', 'Netherlands': '荷兰', 'Germany': '德国',
    'Belgium': '比利时', 'Italy': '意大利', 'Croatia': '克罗地亚', 'Uruguay': '乌拉圭',
    'Morocco': '摩洛哥', 'United States': '美国', 'Mexico': '墨西哥', 'Canada': '加拿大',
    'Japan': '日本', 'South Korea': '韩国', 'Australia': '澳大利亚', 'Senegal': '塞内加尔',
    'Switzerland': '瑞士', 'Denmark': '丹麦', 'Poland': '波兰', 'Colombia': '哥伦比亚',
    'Ecuador': '厄瓜多尔', 'Serbia': '塞尔维亚', 'Ghana': '加纳', 'Nigeria': '尼日利亚',
    'Cameroon': '喀麦隆', 'Ivory Coast': '科特迪瓦', 'Saudi Arabia': '沙特阿拉伯',
    'Qatar': '卡塔尔', 'Iran': '伊朗', 'Tunisia': '突尼斯', 'Egypt': '埃及',
    'Costa Rica': '哥斯达黎加', 'Peru': '秘鲁', 'Chile': '智利', 'Paraguay': '巴拉圭',
    'Algeria': '阿尔及利亚', 'Austria': '奥地利', 'Norway': '挪威', 'Sweden': '瑞典',
    'Turkey': '土耳其', 'Scotland': '苏格兰', 'Wales': '威尔士', 'New Zealand': '新西兰',
    'South Africa': '南非',
}

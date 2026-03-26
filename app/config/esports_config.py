"""赛事推送配置"""
import os

ESPORTS_ENABLED = os.getenv('ESPORTS_ENABLED', 'true').lower() == 'true'
ESPORTS_FETCH_TIMEOUT = int(os.getenv('ESPORTS_FETCH_TIMEOUT', '15'))

# 赛事实时监控
ESPORTS_NBA_MONITOR_INTERVAL = int(os.getenv('ESPORTS_NBA_MONITOR_INTERVAL', '15'))  # 每15分钟检查比分
ESPORTS_LOL_MONITOR_INTERVAL = int(os.getenv('ESPORTS_LOL_MONITOR_INTERVAL', '30'))  # 每30分钟检查比分
ESPORTS_PRE_MATCH_MINUTES = int(os.getenv('ESPORTS_PRE_MATCH_MINUTES', '10'))  # 赛前提醒（开赛前N分钟）

# ESPN NBA API
ESPN_NBA_SCOREBOARD_URL = 'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard'

# LoL Esports API
LOL_ESPORTS_API_BASE = 'https://esports-api.lolesports.com/persisted/gw'
LOL_ESPORTS_API_KEY = '0TvQnueqKa5mxJntVWt0w4LpLfEkrV1Ta8rQBb9Z'

LOL_LEAGUES = {
    'LPL': '98767991314006698',
    'LCK': '98767991310872058',
    'Worlds': '98767975604431411',
    'MSI': '98767991325878492',
    '先锋赛': '113464388705111224',
}

# 常驻显示的联赛（无赛事也显示"无赛事"）
LOL_ALWAYS_SHOW = {'LPL', 'LCK', '先锋赛'}

# NBA 球队监控开关（0=不监控, 1=监控）
# 比赛双方至少有一个被监控的球队才会推送
NBA_TEAM_MONITOR = {
    'Atlanta Hawks': 0,
    'Boston Celtics': 1,
    'Brooklyn Nets': 0,
    'Charlotte Hornets': 0,
    'Chicago Bulls': 0,
    'Cleveland Cavaliers': 1,
    'Dallas Mavericks': 0,
    'Denver Nuggets': 1,
    'Detroit Pistons': 0,
    'Golden State Warriors': 1,
    'Houston Rockets': 1,
    'Indiana Pacers': 0,
    'LA Clippers': 1,
    'Los Angeles Lakers': 1,
    'Memphis Grizzlies': 0,
    'Miami Heat': 0,
    'Milwaukee Bucks': 0,
    'Minnesota Timberwolves': 1,
    'New Orleans Pelicans': 0,
    'New York Knicks': 1,
    'Oklahoma City Thunder':10,
    'Orlando Magic': 0,
    'Philadelphia 76ers': 0,
    'Phoenix Suns': 0,
    'Portland Trail Blazers': 0,
    'Sacramento Kings': 0,
    'San Antonio Spurs': 1,
    'Toronto Raptors': 0,
    'Utah Jazz': 0,
    'Washington Wizards': 0,
}

# NBA 球队英文→中文简称映射
NBA_TEAM_NAMES = {
    'Atlanta Hawks': '老鹰',
    'Boston Celtics': '凯尔特人',
    'Brooklyn Nets': '篮网',
    'Charlotte Hornets': '黄蜂',
    'Chicago Bulls': '公牛',
    'Cleveland Cavaliers': '骑士',
    'Dallas Mavericks': '独行侠',
    'Denver Nuggets': '掘金',
    'Detroit Pistons': '活塞',
    'Golden State Warriors': '勇士',
    'Houston Rockets': '火箭',
    'Indiana Pacers': '步行者',
    'LA Clippers': '快船',
    'Los Angeles Clippers': '快船',
    'Los Angeles Lakers': '湖人',
    'Memphis Grizzlies': '灰熊',
    'Miami Heat': '热火',
    'Milwaukee Bucks': '雄鹿',
    'Minnesota Timberwolves': '森林狼',
    'New Orleans Pelicans': '鹈鹕',
    'New York Knicks': '尼克斯',
    'Oklahoma City Thunder': '雷霆',
    'Orlando Magic': '魔术',
    'Philadelphia 76ers': '76人',
    'Phoenix Suns': '太阳',
    'Portland Trail Blazers': '开拓者',
    'Sacramento Kings': '国王',
    'San Antonio Spurs': '马刺',
    'Toronto Raptors': '猛龙',
    'Utah Jazz': '爵士',
    'Washington Wizards': '奇才',
}

# news_worldcup 推送实现计划（2026 世界杯）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `news_worldcup` 频道，仿 NBA 推送 2026 FIFA 世界杯全部比赛的全套 4 类通知（每日赛程 / 赛前提醒 / 比分变化 / 终场比分）。

**Architecture:** 混合方式 C——数据层独立 `WorldCupService`（足球语义自洽，走 ESPN soccer API，与 NBA 同源同结构），监控调度层 `EsportsMonitorService` 以**加法式分支**纳入 `worldcup` 类型（NBA/LoL 行为保持等价），每日策略与失败重试队列各加 `worldcup` 分支。赛事结束后删独立模块 + 各处 worldcup 分支即净退场。

**Tech Stack:** Python / Flask / httpx / APScheduler / pytest。数据源 ESPN soccer scoreboard。

## Global Constraints

- 频道常量 `news_worldcup`；终场胜方加 🏆 且加粗，平局无 🏆；不标淘汰赛轮次；全部比赛**无球队过滤**。
- 数据源 URL（verbatim）：`https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard`
- 失败语义二分：`None` = 获取失败（已重试耗尽）；空 `{'today': [], 'yesterday': []}` 或空 list = API 成功但无赛事。异常分支 `logger.warning(..., exc_info=True)` 且消息含 `type(e).__name__`。
- 北京时间用 `_CST = timezone(timedelta(hours=8))`；ESPN 用美国日期，需多查几天按北京日期重分类去重。
- 测试运行：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest <path> -v`（env 赋值必须在 `rtk` 之前）。
- 提交：`git add` 与 `git commit` 放进**同一条** Bash 命令链，精确列路径，**不用 `-A`**；命令前加 `rtk`；中文 message 走单行 `-m`；每条 commit 末尾加 trailer `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`（用 `-m "标题" -m "Co-Authored-By: ..."` 双 `-m`）。
- 不写多余注释；不写 backup 文件。

---

### Task 1: 配置与频道常量

**Files:**
- Create: `app/config/worldcup_config.py`
- Modify: `app/config/notification_config.py`（末尾加常量）
- Test: `tests/test_worldcup_config.py`

**Interfaces:**
- Produces:
  - `app.config.notification_config.CHANNEL_WORLDCUP = 'news_worldcup'`
  - `app.config.worldcup_config.WORLDCUP_ENABLED: bool`
  - `app.config.worldcup_config.ESPORTS_WORLDCUP_MONITOR_INTERVAL: int`（默认 5）
  - `app.config.worldcup_config.WORLDCUP_MAX_DURATION_HOURS: int`（默认 3）
  - `app.config.worldcup_config.ESPN_SOCCER_WC_URL: str`
  - `app.config.worldcup_config.WORLDCUP_TEAM_NAMES: dict[str, str]`（英文 displayName → 中文）

- [ ] **Step 1: 写失败测试**

`tests/test_worldcup_config.py`：
```python
def test_channel_constant():
    from app.config.notification_config import CHANNEL_WORLDCUP
    assert CHANNEL_WORLDCUP == 'news_worldcup'


def test_worldcup_config_defaults(monkeypatch):
    monkeypatch.delenv('WORLDCUP_ENABLED', raising=False)
    monkeypatch.delenv('ESPORTS_WORLDCUP_MONITOR_INTERVAL', raising=False)
    import importlib
    import app.config.worldcup_config as wc
    importlib.reload(wc)
    assert wc.WORLDCUP_ENABLED is True
    assert wc.ESPORTS_WORLDCUP_MONITOR_INTERVAL == 5
    assert wc.WORLDCUP_MAX_DURATION_HOURS == 3
    assert wc.ESPN_SOCCER_WC_URL.endswith('soccer/fifa.world/scoreboard')
    assert wc.WORLDCUP_TEAM_NAMES.get('Brazil') == '巴西'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_config.py -v`
Expected: FAIL（`ImportError: cannot import name 'CHANNEL_WORLDCUP'` / `No module named 'app.config.worldcup_config'`）

- [ ] **Step 3: 加频道常量**

在 `app/config/notification_config.py` 末尾（`CHANNEL_RESEARCH = 'news_research'` 之后）追加：
```python
CHANNEL_WORLDCUP = 'news_worldcup'
```

- [ ] **Step 4: 新建 worldcup_config.py**

`app/config/worldcup_config.py`：
```python
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
```
> 实现时若 ESPN 实际 displayName 与上表 key 不符（如 "Korea Republic" 而非 "South Korea"），按实际返回名补 key——未命中只回退英文显示，不报错，可上线后微调。

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_config.py -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 提交**

```bash
rtk git add app/config/worldcup_config.py app/config/notification_config.py tests/test_worldcup_config.py && rtk git commit -m "feat(worldcup): 频道常量与配置" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: WorldCupService 数据层（取数与解析）

**Files:**
- Create: `app/services/worldcup_service.py`
- Test: `tests/test_worldcup_service.py`

**Interfaces:**
- Consumes: `app.config.worldcup_config`（`ESPN_SOCCER_WC_URL` / `WORLDCUP_TEAM_NAMES`），`app.config.esports_config.ESPORTS_FETCH_TIMEOUT`
- Produces:
  - `WorldCupService.get_worldcup_schedule(today=None) -> {'today': list[game], 'yesterday': list[game]} | None`
  - `WorldCupService.get_worldcup_schedule_by_date(target_date) -> list[game] | None`
  - `WorldCupService.get_worldcup_live_scores() -> {match_id: game} | None`
  - `WorldCupService._fetch_soccer_scoreboard(game_date, _max_retries=2) -> list[game] | None`
  - `game` dict 字段：`match_id, home, away, home_score(int|None), away_score(int|None), status('scheduled'|'in_progress'|'completed'), start_time('HH:MM'), _beijing_date(date), status_detail(str), pens((int,int)|None), home_winner(bool), away_winner(bool)`

- [ ] **Step 1: 写失败测试（解析 + 分类）**

`tests/test_worldcup_service.py`（四个测试：解析普通完赛 / 解析点球 / 按北京日期分类 / 全失败返回 None）：
```python
from datetime import date, datetime, timedelta, timezone

from app.services.worldcup_service import WorldCupService

_CST = timezone(timedelta(hours=8))


def _fake_espn(events):
    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {'events': events}
    return _Resp()


def _event(eid, home, away, state, h_score=None, a_score=None,
           short_detail='Scheduled', start='2026-06-20T00:00Z',
           h_pen=None, a_pen=None, h_win=False, a_win=False):
    def comp(side, name, score, pen, win):
        c = {'homeAway': side, 'team': {'displayName': name}, 'winner': win}
        if score is not None:
            c['score'] = str(score)
        if pen is not None:
            c['shootoutScore'] = str(pen)
        return c
    return {
        'id': eid,
        'date': start,
        'status': {'type': {'state': state, 'shortDetail': short_detail}},
        'competitions': [{'competitors': [
            comp('home', home, h_score, h_pen, h_win),
            comp('away', away, a_score, a_pen, a_win),
        ]}],
    }


def test_parse_completed_event_fields(monkeypatch):
    ev = _event('1', 'Brazil', 'United States', 'post', 2, 1,
                short_detail='FT', start='2026-06-20T01:00Z', h_win=True)
    monkeypatch.setattr('httpx.get', lambda *a, **k: _fake_espn([ev]))
    games = WorldCupService._fetch_soccer_scoreboard(date(2026, 6, 20))
    assert len(games) == 1
    g = games[0]
    assert g['home'] == '巴西' and g['away'] == '美国'
    assert g['home_score'] == 2 and g['away_score'] == 1
    assert g['status'] == 'completed'
    assert g['home_winner'] is True and g['away_winner'] is False
    assert g['pens'] is None
    assert g['match_id'] == '1'


def test_parse_penalty_event(monkeypatch):
    ev = _event('9', 'Brazil', 'Spain', 'post', 1, 1,
                short_detail='FT', h_pen=4, a_pen=2, start='2026-07-01T01:00Z')
    monkeypatch.setattr('httpx.get', lambda *a, **k: _fake_espn([ev]))
    games = WorldCupService._fetch_soccer_scoreboard(date(2026, 7, 1))
    assert games[0]['pens'] == (4, 2)


def test_get_schedule_classifies_by_beijing_date(monkeypatch):
    today = datetime.now(_CST).date()
    yest = today - timedelta(days=1)

    def fake_fetch(game_date, _max_retries=2):
        return [
            {'match_id': 't', 'home': '巴西', 'away': '法国', 'status': 'scheduled',
             'start_time': '08:30', '_beijing_date': today, 'home_score': None,
             'away_score': None, 'status_detail': 'Scheduled', 'pens': None,
             'home_winner': False, 'away_winner': False},
            {'match_id': 'y', 'home': '西班牙', 'away': '意大利', 'status': 'completed',
             'start_time': '03:00', '_beijing_date': yest, 'home_score': 0,
             'away_score': 0, 'status_detail': 'FT', 'pens': None,
             'home_winner': False, 'away_winner': False},
        ]

    monkeypatch.setattr(WorldCupService, '_fetch_soccer_scoreboard', staticmethod(fake_fetch))
    sched = WorldCupService.get_worldcup_schedule(today=today)
    assert [g['match_id'] for g in sched['today']] == ['t']
    assert [g['match_id'] for g in sched['yesterday']] == ['y']


def test_get_schedule_all_fail_returns_none(monkeypatch):
    monkeypatch.setattr(WorldCupService, '_fetch_soccer_scoreboard',
                        staticmethod(lambda d, _max_retries=2: None))
    assert WorldCupService.get_worldcup_schedule() is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_service.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'app.services.worldcup_service'`）

- [ ] **Step 3: 实现 WorldCupService**

`app/services/worldcup_service.py`：
```python
"""2026 FIFA 世界杯赛事数据（ESPN soccer 源，临时赛事结束后整文件删除）"""
import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config.esports_config import ESPORTS_FETCH_TIMEOUT
from app.config.worldcup_config import ESPN_SOCCER_WC_URL, WORLDCUP_TEAM_NAMES

logger = logging.getLogger(__name__)

_CST = timezone(timedelta(hours=8))

# ESPN shortDetail → 中文状态尾标；分钟串（如 "67'"）不在表中则原样透传
_STATUS_CN = {
    'HT': '中场', 'Halftime': '中场',
    'FT': '终场', 'Full Time': '终场',
    'AET': '加时结束', 'Pens': '点球',
}


class WorldCupService:
    """获取 2026 世界杯赛程与实时比分"""

    @staticmethod
    def get_worldcup_schedule(today=None):
        """今日赛程 + 昨日结果；全部失败返回 None"""
        if today is None:
            today = datetime.now(_CST).date()
        yesterday = today - timedelta(days=1)

        all_games = []
        any_success = False
        for offset in range(3):
            d = today - timedelta(days=offset)
            games = WorldCupService._fetch_soccer_scoreboard(d)
            if games is not None:
                any_success = True
                all_games.extend(games)
        if not any_success:
            return None

        result = {'today': [], 'yesterday': []}
        seen = set()
        for game in all_games:
            beijing_date = game.pop('_beijing_date', None)
            key = (game['home'], game['away'], game.get('start_time'))
            if key in seen:
                continue
            seen.add(key)
            if beijing_date == today:
                result['today'].append(game)
            elif beijing_date == yesterday:
                result['yesterday'].append(game)
        return result

    @staticmethod
    def get_worldcup_schedule_by_date(target_date):
        """指定北京日期赛程；失败返回 None"""
        all_games = []
        any_success = False
        for offset in [-1, 0]:
            d = target_date + timedelta(days=offset)
            games = WorldCupService._fetch_soccer_scoreboard(d)
            if games is not None:
                any_success = True
                all_games.extend(games)
        if not any_success:
            return None

        result = []
        seen = set()
        for game in all_games:
            beijing_date = game.pop('_beijing_date', None)
            key = (game['home'], game['away'], game.get('start_time'))
            if key in seen:
                continue
            seen.add(key)
            if beijing_date == target_date:
                result.append(game)
        return result

    @staticmethod
    def get_worldcup_live_scores():
        """当天所有比赛实时比分 {match_id: game}；失败返回 None"""
        today = datetime.now(_CST).date()
        all_games = []
        any_success = False
        for offset in range(3):
            d = today - timedelta(days=offset)
            games = WorldCupService._fetch_soccer_scoreboard(d)
            if games is not None:
                any_success = True
                all_games.extend(games)
        if not any_success:
            return None
        seen = set()
        result = {}
        for g in all_games:
            g.pop('_beijing_date', None)
            mid = g.get('match_id')
            if mid and mid not in seen:
                seen.add(mid)
                result[mid] = g
        return result

    @staticmethod
    def _fetch_soccer_scoreboard(game_date, _max_retries=2):
        """拉取指定日期 ESPN soccer scoreboard；失败返回 None"""
        date_str = game_date.strftime('%Y%m%d')
        for attempt in range(_max_retries + 1):
            try:
                return WorldCupService._do_fetch_soccer(date_str)
            except Exception as e:
                if attempt < _max_retries:
                    logger.info(f'[世界杯] ESPN第{attempt + 1}次获取失败，重试: '
                                f'{type(e).__name__}: {e}')
                    time.sleep(2)
                else:
                    logger.warning(f'[世界杯] ESPN获取失败（已重试{_max_retries}次）: '
                                   f'{type(e).__name__}: {e}', exc_info=True)
                    return None

    @staticmethod
    def _do_fetch_soccer(date_str):
        resp = httpx.get(ESPN_SOCCER_WC_URL, params={'dates': date_str},
                         timeout=ESPORTS_FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        game_date = datetime.strptime(date_str, '%Y%m%d').date()

        games = []
        for event in data.get('events', []):
            competition = event.get('competitions', [{}])[0]
            competitors = competition.get('competitors', [])
            if len(competitors) < 2:
                continue

            home_info = away_info = None
            for c in competitors:
                if c.get('homeAway') == 'home':
                    home_info = c
                elif c.get('homeAway') == 'away':
                    away_info = c
            if not home_info or not away_info:
                continue

            home_name = home_info.get('team', {}).get('displayName', '')
            away_name = away_info.get('team', {}).get('displayName', '')
            home_cn = WORLDCUP_TEAM_NAMES.get(home_name, home_name)
            away_cn = WORLDCUP_TEAM_NAMES.get(away_name, away_name)

            status_obj = event.get('status', {})
            state = status_obj.get('type', {}).get('state', '')
            short_detail = status_obj.get('type', {}).get('shortDetail', '')

            start_utc = event.get('date', '')
            start_time = ''
            beijing_date = game_date
            if start_utc:
                try:
                    dt = datetime.fromisoformat(start_utc.replace('Z', '+00:00'))
                    start_time = dt.astimezone(_CST).strftime('%H:%M')
                    beijing_date = dt.astimezone(_CST).date()
                except (ValueError, TypeError):
                    pass

            if state == 'post':
                status = 'completed'
            elif state == 'in':
                status = 'in_progress'
            else:
                status = 'scheduled'

            game = {
                'match_id': event.get('id', ''),
                'home': home_cn,
                'away': away_cn,
                'status': status,
                'start_time': start_time,
                '_beijing_date': beijing_date,
                'home_score': None,
                'away_score': None,
                'status_detail': short_detail,
                'pens': None,
                'home_winner': bool(home_info.get('winner')),
                'away_winner': bool(away_info.get('winner')),
            }
            if state in ('post', 'in'):
                try:
                    game['home_score'] = int(home_info.get('score', 0))
                    game['away_score'] = int(away_info.get('score', 0))
                except (ValueError, TypeError):
                    pass
                hp = home_info.get('shootoutScore')
                ap = away_info.get('shootoutScore')
                if hp is not None and ap is not None:
                    try:
                        game['pens'] = (int(hp), int(ap))
                    except (ValueError, TypeError):
                        pass
            games.append(game)
        return games
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_service.py -v`
Expected: PASS（4 passed：parse_completed / parse_penalty / classify / all_fail）

- [ ] **Step 5: 提交**

```bash
rtk git add app/services/worldcup_service.py tests/test_worldcup_service.py && rtk git commit -m "feat(worldcup): WorldCupService 取数与解析（ESPN soccer）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 足球比分格式化 `format_score`

**Files:**
- Modify: `app/services/worldcup_service.py`（在 `WorldCupService` 内加静态方法）
- Test: `tests/test_worldcup_service.py`（追加格式测试）

**Interfaces:**
- Consumes: Task 2 的 `game` dict 结构 + 模块级 `_STATUS_CN`
- Produces: `WorldCupService.format_score(game, final=False) -> str`（返回含 `⚽` 前缀的完整 Slack 文案）

- [ ] **Step 1: 追加失败测试**

在 `tests/test_worldcup_service.py` 末尾追加：
```python
def _g(home, away, hs, aws, **kw):
    base = {'home': home, 'away': away, 'home_score': hs, 'away_score': aws,
            'status_detail': '', 'pens': None, 'home_winner': False,
            'away_winner': False}
    base.update(kw)
    return base


def test_format_in_progress_bolds_leader():
    s = WorldCupService.format_score(_g('巴西', '中国', 1, 0, status_detail="67'"))
    assert s.startswith('⚽')
    assert '*巴西 1*' in s
    assert "67'" in s and '终场' not in s


def test_format_in_progress_translates_ht():
    s = WorldCupService.format_score(_g('巴西', '中国', 0, 0, status_detail='HT'))
    assert '中场' in s


def test_format_final_draw_no_trophy():
    s = WorldCupService.format_score(_g('中国', '巴西', 1, 1, status_detail='FT'), final=True)
    assert '🏆' not in s
    assert '终场' in s
    assert '中国 1 - 1 巴西' in s


def test_format_final_winner_trophy():
    s = WorldCupService.format_score(
        _g('巴西', '中国', 2, 1, status_detail='FT', home_winner=True), final=True)
    assert '🏆' in s and '*' in s
    assert '巴西' in s and '终场' in s
    # 胜方在加粗段内
    bold = s.split('*')[1]
    assert '巴西' in bold and '2' in bold


def test_format_penalty_winner_by_pens():
    s = WorldCupService.format_score(
        _g('巴西', '中国', 1, 1, status_detail='FT', pens=(4, 2)), final=True)
    assert '点球' in s
    assert '(4)' in s and '(2)' in s
    assert '🏆' in s
    bold = s.split('*')[1]
    assert '巴西' in bold  # 点球胜方加粗
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_service.py -k format -v`
Expected: FAIL（`AttributeError: ... has no attribute 'format_score'`）

- [ ] **Step 3: 实现 format_score**

在 `WorldCupService` 类内（`get_worldcup_schedule` 之前或之后均可）加：
```python
    @staticmethod
    def format_score(game, final=False):
        """足球比分文案。主队在左。final 时胜方加 🏆+加粗，平局无 🏆。

        进行中：⚽ *巴西 1* - 0 中国 | 67'
        平局终场：⚽ 中国 1 - 1 巴西 | 终场
        胜负终场：⚽ *🏆 巴西 2* - 1 中国 | 终场
        点球：  ⚽ *🏆 巴西 1(4)* - 1(2) 中国 | 点球
        """
        t1, s1 = game['home'], game.get('home_score') or 0
        t2, s2 = game['away'], game.get('away_score') or 0
        pens = game.get('pens')
        p1 = f'({pens[0]})' if pens else ''
        p2 = f'({pens[1]})' if pens else ''

        if final:
            tail = ' | 点球' if pens else ' | 终场'
        else:
            detail = game.get('status_detail') or ''
            cn = _STATUS_CN.get(detail, detail)
            tail = f' | {cn}' if cn else ''

        if pens:
            w1, w2 = pens[0] > pens[1], pens[1] > pens[0]
        elif final:
            w1 = bool(game.get('home_winner')) or s1 > s2
            w2 = bool(game.get('away_winner')) or s2 > s1
        else:
            w1, w2 = s1 > s2, s2 > s1

        trophy = '🏆 ' if final else ''
        if w1:
            body = f'*{trophy}{t1} {s1}{p1}* - {s2}{p2} {t2}'
        elif w2:
            body = f'{t1} {s1}{p1} - *{s2}{p2} {trophy}{t2}*'
        else:
            body = f'{t1} {s1}{p1} - {s2}{p2} {t2}'
        return f'⚽ {body}{tail}'
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_service.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 提交**

```bash
rtk git add app/services/worldcup_service.py tests/test_worldcup_service.py && rtk git commit -m "feat(worldcup): 足球比分格式化（平局/胜负🏆/点球）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 每日赛程预告 `_push_worldcup_today`

**Files:**
- Modify: `app/strategies/esports_daily_schedule/__init__.py`
- Test: `tests/test_esports_daily_schedule_routing.py`（追加 worldcup 用例）

**Interfaces:**
- Consumes: `WorldCupService.get_worldcup_schedule`，`CHANNEL_WORLDCUP`，`esports_retry_queue.enqueue`（`kind='worldcup'`, `name='WorldCup'`）
- Produces: `EsportsDailyScheduleStrategy._push_worldcup_today()`（静态方法），并在 `scan()` 中调用

- [ ] **Step 1: 追加失败测试**

在 `tests/test_esports_daily_schedule_routing.py` 末尾追加：
```python
def test_worldcup_failure_enqueues(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: None),
    )
    EsportsDailyScheduleStrategy._push_worldcup_today()
    assert cap.calls == []
    today = datetime.now(_CST).date()
    assert rq._key(today, 'worldcup', 'WorldCup') in rq._pending


def test_worldcup_success_pushes(monkeypatch):
    cap = _patch_slack(monkeypatch)
    fake = {'today': [{'home': '巴西', 'away': '中国', 'start_time': '08:00'}],
            'yesterday': []}
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: fake),
    )
    EsportsDailyScheduleStrategy._push_worldcup_today()
    assert len(cap.calls) == 1
    text, channel = cap.calls[0]
    assert channel == 'news_worldcup'
    assert '巴西 vs 中国' in text and '08:00' in text
    assert rq._pending == {}


def test_worldcup_empty_pushes_no_match(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: {'today': [], 'yesterday': []}),
    )
    EsportsDailyScheduleStrategy._push_worldcup_today()
    assert len(cap.calls) == 1
    assert '今日无比赛' in cap.calls[0][0]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_esports_daily_schedule_routing.py -k worldcup -v`
Expected: FAIL（`AttributeError: ... has no attribute '_push_worldcup_today'`）

- [ ] **Step 3: 实现 `_push_worldcup_today` 并接入 `scan()`**

在 `scan()` 方法体内（`self._push_lol_today()` 之后、`return []` 之前）加：
```python
        self._push_worldcup_today()
```

在类内追加静态方法（放在 `_push_lol_today` 之后）：
```python
    @staticmethod
    def _push_worldcup_today():
        from app.services.worldcup_service import WorldCupService
        from app.services.notification import NotificationService
        from app.config.notification_config import CHANNEL_WORLDCUP
        from app.services.esports_retry_queue import enqueue

        try:
            sched = WorldCupService.get_worldcup_schedule()
            if sched is None:
                today = datetime.now(_CST).date()
                enqueue(today, 'worldcup', 'WorldCup')
                return

            games = sched.get('today') or []
            if not games:
                NotificationService.send_slack(
                    '⚽ *今日世界杯赛程*\n今日无比赛', CHANNEL_WORLDCUP)
                return

            lines = [f'⚽ *今日世界杯赛程* ({len(games)}场)', '']
            for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
                t = g.get('start_time') or '--:--'
                lines.append(f'  · {t}  {g["home"]} vs {g["away"]}')
            NotificationService.send_slack('\n'.join(lines), CHANNEL_WORLDCUP)
            logger.info(f'[赛事安排] 世界杯 推送 {len(games)} 场')
        except Exception as e:
            logger.error(f'[赛事安排] 世界杯 推送失败: {type(e).__name__}: {e}',
                         exc_info=True)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_esports_daily_schedule_routing.py -v`
Expected: PASS（原 4 + 新 3 = 7 passed）

- [ ] **Step 5: 提交**

```bash
rtk git add app/strategies/esports_daily_schedule/__init__.py tests/test_esports_daily_schedule_routing.py && rtk git commit -m "feat(worldcup): 每日赛程预告接入 esports_daily_schedule" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 失败重试队列 worldcup 分支

**Files:**
- Modify: `app/services/esports_retry_queue.py`
- Test: `tests/test_esports_retry_queue.py`（追加 worldcup 用例）

**Interfaces:**
- Consumes: `WorldCupService.get_worldcup_schedule`，`CHANNEL_WORLDCUP`，Task 4 入队的 `kind='worldcup'`
- Produces: `_refetch` / `_push_supplement` / `_push_failed` 支持 `unit.kind == 'worldcup'`；新增 `_push_worldcup_supplement(matches)`

- [ ] **Step 1: 查看现有重试测试风格**

Read `tests/test_esports_retry_queue.py`（确认 fixture / monkeypatch `_schedule_retry` / `_refetch` 的既有写法，新用例与之对齐）。

- [ ] **Step 2: 追加失败测试**

在 `tests/test_esports_retry_queue.py` 末尾追加（如文件已有 `_patch_slack` / `_SlackCapture` 等辅助，复用之；否则仿 `test_esports_daily_schedule_routing.py` 的 `_SlackCapture`）：
```python
def test_worldcup_supplement_pushes(monkeypatch):
    from app.services import notification
    calls = []
    monkeypatch.setattr(notification.NotificationService, 'send_slack',
                        staticmethod(lambda m, c, blocks=None: calls.append((m, c))))
    fake = {'today': [{'home': '巴西', 'away': '中国', 'start_time': '08:00'}],
            'yesterday': []}
    rq._push_supplement(rq._PendingUnit(date=date.today(), kind='worldcup',
                                        name='WorldCup'), fake)
    assert calls and calls[0][1] == 'news_worldcup'
    assert '巴西 vs 中国' in calls[0][0]


def test_worldcup_refetch_calls_service(monkeypatch):
    sentinel = {'today': [], 'yesterday': []}
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: sentinel),
    )
    out = rq._refetch(rq._PendingUnit(date=date.today(), kind='worldcup',
                                      name='WorldCup'))
    assert out is sentinel
```
> 若 `test_esports_retry_queue.py` 顶部未 `import app.services.esports_retry_queue as rq` 或缺 `from datetime import date`，按现有导入补齐。

- [ ] **Step 3: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_esports_retry_queue.py -k worldcup -v`
Expected: FAIL（`_refetch` 对 worldcup 返回 None → `out is sentinel` 失败；`_push_supplement` worldcup 无分支 → 无推送）

- [ ] **Step 4: 实现 worldcup 分支**

`app/services/esports_retry_queue.py`：

在 `_refetch` 的 `if unit.kind == 'nba': ...` 之后、`return None` 之前加：
```python
    if unit.kind == 'worldcup':
        from app.services.worldcup_service import WorldCupService
        return WorldCupService.get_worldcup_schedule(today=unit.date)
```

在 `_push_supplement` 加分支：
```python
    elif unit.kind == 'worldcup':
        _push_worldcup_supplement(matches)
```

新增函数（放在 `_push_nba_supplement` 之后）：
```python
def _push_worldcup_supplement(sched):
    from app.services.notification import NotificationService
    from app.config.notification_config import CHANNEL_WORLDCUP

    games = sched.get('today') or []
    if not games:
        NotificationService.send_slack('⚽ *世界杯 补充*\n今日无比赛', CHANNEL_WORLDCUP)
        return
    lines = [f'⚽ *世界杯 补充* ({len(games)}场)']
    for g in sorted(games, key=lambda x: x.get('start_time') or '99:99'):
        t = g.get('start_time') or '--:--'
        lines.append(f'  · {t}  {g["home"]} vs {g["away"]}')
    NotificationService.send_slack('\n'.join(lines), CHANNEL_WORLDCUP)
```

在 `_push_failed` 加分支（在 nba 分支之后），并补 import：
```python
    elif unit.kind == 'worldcup':
        NotificationService.send_slack(
            f'⚽ *今日世界杯赛程* 数据获取失败（已重试 {_MAX_ATTEMPTS} 次）',
            CHANNEL_WORLDCUP,
        )
```
将 `_push_failed` 顶部的 `from app.config.notification_config import CHANNEL_LOL, CHANNEL_NBA` 改为：
```python
    from app.config.notification_config import CHANNEL_LOL, CHANNEL_NBA, CHANNEL_WORLDCUP
```
并把 `_PendingUnit` 的 docstring 注释 `# 'lol' | 'nba'` 更新为 `# 'lol' | 'nba' | 'worldcup'`。

- [ ] **Step 5: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_esports_retry_queue.py -v`
Expected: PASS（原有 + 新 2 全过）

- [ ] **Step 6: 提交**

```bash
rtk git add app/services/esports_retry_queue.py tests/test_esports_retry_queue.py && rtk git commit -m "feat(worldcup): 失败重试队列 worldcup 分支" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 监控调度层纳入 worldcup（赛前提醒 + 比分轮询）

**Files:**
- Modify: `app/services/esports_monitor_service.py`
- Test: `tests/test_worldcup_monitor.py`

**Interfaces:**
- Consumes: `WorldCupService.get_worldcup_schedule` / `get_worldcup_schedule_by_date` / `get_worldcup_live_scores` / `format_score`，`CHANNEL_WORLDCUP`，`ESPORTS_WORLDCUP_MONITOR_INTERVAL`，`WORLDCUP_MAX_DURATION_HOURS`
- Produces:
  - `EsportsMonitorService._poll_worldcup_match(self, match_id, job_id, NotificationService, channel, scheduler_engine)`
  - `setup_match_monitors(match_type='worldcup'|None)` 纳入世界杯比赛
  - `_push_pre_match_notification` 支持 `match_type='worldcup'`（emoji `⚽`，channel `news_worldcup`，无 league 前缀）

> **策略：加法式分支，保持 NBA/LoL 行为字节级等价。** 不重构为大 meta 表，仅把现有二元条件扩成三元、并新增 worldcup 专用轮询方法。

- [ ] **Step 1: 写失败测试**

`tests/test_worldcup_monitor.py`：
```python
from datetime import datetime, timedelta, timezone

from flask import Flask

from app.services.esports_monitor_service import EsportsMonitorService

_CST = timezone(timedelta(hours=8))


def _svc():
    return EsportsMonitorService(Flask(__name__))


def test_prematch_worldcup_routes_to_channel(monkeypatch):
    calls = []
    from app.services import notification
    monkeypatch.setattr(notification.NotificationService, 'send_slack',
                        staticmethod(lambda m, c, blocks=None: calls.append((m, c))))
    _svc()._push_pre_match_notification('worldcup', 'm1', '巴西 vs 中国',
                                        'WorldCup', '08:00')
    assert len(calls) == 1
    msg, channel = calls[0]
    assert channel == 'news_worldcup'
    assert msg.startswith('⚽')
    assert '[' not in msg.split('|')[0]  # 无 league 前缀
    assert '巴西 vs 中国' in msg


def test_poll_worldcup_in_progress_pushes_score(monkeypatch):
    calls = []
    from app.services import notification
    monkeypatch.setattr(notification.NotificationService, 'send_slack',
                        staticmethod(lambda m, c, blocks=None: calls.append((m, c))))
    live = {'m1': {'home': '巴西', 'away': '中国', 'home_score': 1,
                   'away_score': 0, 'status': 'in_progress', 'status_detail': "67'",
                   'pens': None, 'home_winner': False, 'away_winner': False}}
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_live_scores',
        staticmethod(lambda: live),
    )
    # 清理可能残留的比分状态
    import app.services.esports_monitor_service as mod
    with mod._score_state_lock:
        mod._score_state.clear()

    future = datetime.now(_CST) + timedelta(hours=1)
    _svc()._poll_match('worldcup', 'm1', '巴西 vs 中国', 'WorldCup', future)
    assert len(calls) == 1
    msg, channel = calls[0]
    assert channel == 'news_worldcup'
    assert msg.startswith('⚽') and '*巴西 1*' in msg
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_monitor.py -v`
Expected: FAIL（`_push_pre_match_notification` 把 worldcup 当 lol 路由到 `news_lol`；`_poll_match` 把 worldcup 当 lol 调 `_poll_lol_match` 取不到 live → 无推送）

- [ ] **Step 3: 改 `esports_monitor_service.py`**

**(a) 顶部 import** 增加 worldcup 配置（与现有 esports_config import 并列）：
```python
from app.config.worldcup_config import (
    ESPORTS_WORLDCUP_MONITOR_INTERVAL, WORLDCUP_MAX_DURATION_HOURS,
)
```

**(b) 类常量** 在 `LOL_MAX_DURATION_HOURS = 8` 之后加（用别名避免与导入名重名）：
```python
    WC_MAX_DURATION_HOURS = WORLDCUP_MAX_DURATION_HOURS
```

**(c) `setup_match_monitors`** 在 LoL 拉取块（`if not match_type or match_type == 'lol':` 整段）之后加 worldcup 拉取块：
```python
        if not match_type or match_type == 'worldcup':
            try:
                from app.services.worldcup_service import WorldCupService
                if is_today:
                    wc = WorldCupService.get_worldcup_schedule()
                    wc_games = wc.get('today', []) if wc else []
                else:
                    wc_games = WorldCupService.get_worldcup_schedule_by_date(target_date) or []
                for game in wc_games:
                    if game.get('match_id') and game['status'] != 'completed':
                        matches.append({
                            'match_id': game['match_id'],
                            'match_type': 'worldcup',
                            'status': game['status'],
                            'start_time': game.get('start_time', ''),
                            'game_date': target_date,
                            'teams_desc': f"{game['home']} vs {game['away']}",
                            'league': 'WorldCup',
                        })
            except Exception as e:
                logger.warning(f'[赛事监控] 世界杯赛程获取失败: {type(e).__name__}: {e}')
```
> 无球队过滤（全部比赛）。`is_today` 分支与 NBA 一致：今天用 `get_worldcup_schedule`，非今天（22:00 次日 setup）用 `get_worldcup_schedule_by_date`。

**(d) `_create_monitor_job` 的 interval / max_hours** 把两处二元条件扩成三元：
```python
        if match_type == 'nba':
            interval = ESPORTS_NBA_MONITOR_INTERVAL
        elif match_type == 'lol':
            interval = ESPORTS_LOL_MONITOR_INTERVAL
        else:
            interval = ESPORTS_WORLDCUP_MONITOR_INTERVAL
```
（替换原 `interval = ESPORTS_NBA_MONITOR_INTERVAL if match_type == 'nba' else ESPORTS_LOL_MONITOR_INTERVAL`）

```python
        if match_type == 'nba':
            max_hours = self.NBA_MAX_DURATION_HOURS
        elif match_type == 'lol':
            max_hours = self.LOL_MAX_DURATION_HOURS
        else:
            max_hours = self.WC_MAX_DURATION_HOURS
```
（替换原 `max_hours = self.NBA_MAX_DURATION_HOURS if match_type == 'nba' else self.LOL_MAX_DURATION_HOURS`）

**(e) `_push_pre_match_notification`** 改频道/emoji/前缀映射：
```python
                from app.config.notification_config import (
                    CHANNEL_NBA, CHANNEL_LOL, CHANNEL_WORLDCUP,
                )

                if match_type == 'nba':
                    channel, emoji = CHANNEL_NBA, '🏀'
                elif match_type == 'lol':
                    channel, emoji = CHANNEL_LOL, '🎮'
                else:
                    channel, emoji = CHANNEL_WORLDCUP, '⚽'
                league_prefix = f'[{league}] ' if match_type == 'lol' else ''
```
（替换原 `channel = CHANNEL_NBA if match_type == 'nba' else CHANNEL_LOL`、`emoji = '🏀' if ... else '🎮'`、`league_prefix` 三行）

**(f) `_poll_match`** 扩展分发：
```python
                from app.config.notification_config import (
                    CHANNEL_NBA, CHANNEL_LOL, CHANNEL_WORLDCUP,
                )

                if match_type == 'nba':
                    self._poll_nba_match(match_id, job_id, EsportsService, NotificationService, CHANNEL_NBA, scheduler_engine)
                elif match_type == 'lol':
                    self._poll_lol_match(match_id, job_id, league, EsportsService, NotificationService, CHANNEL_LOL, scheduler_engine)
                else:
                    self._poll_worldcup_match(match_id, job_id, NotificationService, CHANNEL_WORLDCUP, scheduler_engine)
```
（替换原 import 行与 if/else 两分支）

**(g) 新增 `_poll_worldcup_match`**（放在 `_poll_lol_match` 之后）：
```python
    def _poll_worldcup_match(self, match_id, job_id, NotificationService, channel, scheduler_engine):
        """轮询世界杯比赛（进行中比分变化推送 + 终场比分）"""
        from app.services.worldcup_service import WorldCupService

        scores = WorldCupService.get_worldcup_live_scores()
        if scores is None:
            logger.warning('[赛事监控] 世界杯比分获取失败')
            return

        game = scores.get(match_id)
        if game is None:
            logger.warning(f'[赛事监控] 未找到比赛 {match_id}')
            return

        home_score = game.get('home_score') or 0
        away_score = game.get('away_score') or 0
        status = game['status']

        if status == 'completed':
            # 足球可 0:0 收场（小组赛平局），终场一律推送
            msg = WorldCupService.format_score(game, final=True)
            NotificationService.send_slack(msg, channel)
            _clear_score('worldcup', match_id)
            scheduler_engine.scheduler.remove_job(job_id)
            logger.info(f'[赛事监控] {job_id} 比赛结束，移除')
            return

        if status == 'in_progress':
            if _has_score_changed('worldcup', match_id, home_score, away_score, status):
                msg = WorldCupService.format_score(game, final=False)
                NotificationService.send_slack(msg, channel)
                _update_score('worldcup', match_id, home_score, away_score, status)
                logger.info(f'[赛事监控] 世界杯比分变化: {game["home"]} '
                            f'{home_score}-{away_score} {game["away"]}')
            else:
                logger.debug(f'[赛事监控] {job_id} 比分未变化，跳过推送')
```
> `_has_score_changed` 对 0:0 返回 False（首个进球才推），与 NBA 一致；终场分支不受其约束，0:0 平局也推。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_monitor.py -v`
Expected: PASS（2 passed）

- [ ] **Step 5: NBA/LoL 回归校验**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_esports_daily_schedule_routing.py tests/test_esports_retry_queue.py tests/test_worldcup_service.py tests/test_worldcup_monitor.py -v`
Expected: 全 PASS（无 NBA/LoL 路由回归）

- [ ] **Step 6: 提交**

```bash
rtk git add app/services/esports_monitor_service.py tests/test_worldcup_monitor.py && rtk git commit -m "feat(worldcup): 监控调度纳入 worldcup（赛前提醒+比分轮询）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 调度引擎复核 + 文档同步 + 全量验证

**Files:**
- Verify（预计无需改）: `app/scheduler/engine.py`
- Modify: `.claude/rules/esports.md`，`README.md`，`.env.sample`

**Interfaces:**
- Consumes: 全部前序任务

- [ ] **Step 1: 复核调度引擎是否自动覆盖 worldcup**

Read `app/scheduler/engine.py` 的 `_setup_esports_monitors_safe`（约 155–160 行）、`_setup_esports_monitors_tomorrow`（约 172–181）、`_recover_esports_monitors`（146–151）。确认它们调用 `setup_match_monitors()`（无 `match_type` 参数 = None = 全类型）。
- 若均为无参调用：Task 6 的 `setup_match_monitors` 已自动纳入 worldcup（5:00 早间 / 22:00 次日 / 启动恢复 三处覆盖凌晨与白天场次）。**无需改 engine。** 在本步骤的提交说明里记一句"engine 复核：默认 setup 自动覆盖 worldcup，无需改动"。
- 若发现某调用显式传了 `match_type='nba'`/`'lol'` 而漏掉 worldcup：在该处补一次 `setup_match_monitors(match_type='worldcup')` 调用（仿 `_setup_nba_evening_monitors` 的写法），并在本任务追加一条说明。

- [ ] **Step 2: 更新 `.claude/rules/esports.md`**

在文件标题改为涵盖世界杯，并在"赛事推送配置"表后补一段：
```markdown
## 世界杯推送（2026 FIFA，临时）

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WORLDCUP_ENABLED` | 是否启用世界杯推送 | `true` |
| `ESPORTS_WORLDCUP_MONITOR_INTERVAL` | 世界杯比分轮询间隔（分钟） | `5` |

- 数据源：ESPN soccer `fifa.world` scoreboard（与 NBA 同源同结构）。数据层独立 `app/services/worldcup_service.py`，足球语义（平局/点球/上下半场状态）自洽，不污染 NBA/LoL。
- 推送：每日赛程预告（07:00，并入 `esports_daily_schedule`）→ `news_worldcup`；赛前 30min 提醒（共享 `ESPORTS_PRE_MATCH_MINUTES`）；进球/比分变化；终场比分（胜方加 🏆，平局无 🏆，点球括号标注）。全部比赛无球队过滤。
- 监控调度：`EsportsMonitorService` 以加法式分支纳入 `match_type='worldcup'`，复用赛前提醒/比分轮询/重试队列框架。WC2026 在美加墨，北京时间多落 00:00–11:00，靠 22:00 次日 setup 覆盖凌晨场次、5:00 早间 setup 覆盖白天场次。
- 退场：赛事结束后删 `worldcup_service.py` + `worldcup_config.py` + 各文件 worldcup 分支与 `CHANNEL_WORLDCUP`。
```

- [ ] **Step 3: 更新 `README.md` 频道表**

在 README 的 Slack 频道表（含 `news_nba` / `news_lol` 行）后加一行：
```markdown
| `news_worldcup` | 2026 世界杯赛程/比分 |
```
> 先 Grep `news_nba` 定位 README 的频道表与赛事配置段，按其既有格式补 `WORLDCUP_ENABLED` / `ESPORTS_WORLDCUP_MONITOR_INTERVAL` 两个环境变量说明（若 README 有赛事环境变量表）。

- [ ] **Step 4: 更新 `.env.sample`**

Grep `ESPORTS_` 定位赛事变量段，在其后加：
```bash
# 2026 世界杯推送（临时赛事）
WORLDCUP_ENABLED=true
ESPORTS_WORLDCUP_MONITOR_INTERVAL=5
```

- [ ] **Step 5: 全量测试**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_worldcup_config.py tests/test_worldcup_service.py tests/test_worldcup_monitor.py tests/test_esports_daily_schedule_routing.py tests/test_esports_retry_queue.py -v > .omc/artifacts/wc_test.txt 2>&1; grep -E "passed|failed|error" .omc/artifacts/wc_test.txt
```
Expected: 全 PASS，无 failed/error（结果写文件再 grep，规避 Windows 管道吞 stdout）

- [ ] **Step 6: 提交**

```bash
rtk git add .claude/rules/esports.md README.md .env.sample && rtk git commit -m "docs(worldcup): esports 规则/README/env.sample 同步 + engine 复核" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
> 若 Step 1 确实改了 `app/scheduler/engine.py`，把它加入本次 `git add` 路径。

---

## 自检（spec 覆盖）

| Spec 段 | 对应 Task |
|---|---|
| §1 频道 news_worldcup | Task 1 |
| §2 worldcup_config 配置 | Task 1 |
| §3 WorldCupService 取数/解析 | Task 2 |
| §4 足球比分格式（平局/胜负🏆/点球） | Task 3 |
| §5 监控层泛化（setup/prematch/poll/max_hours） | Task 6 |
| §6 每日赛程预告 | Task 4 |
| §7 失败重试 worldcup 分支 | Task 5 |
| §8 调度引擎复核 | Task 7 |
| §9 测试 | Task 2/3/4/5/6/7 |
| §10 文档同步 | Task 7 |

退场清单见 spec §退场清单。非目标（无球队过滤/不标轮次/不做长期足球框架/比分状态不持久化）已在各 Task 落实。

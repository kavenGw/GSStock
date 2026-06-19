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


def test_format_in_progress_bolds_away_leader():
    s = WorldCupService.format_score(_g('巴西', '中国', 0, 2, status_detail="80'"))
    assert s.startswith('⚽')
    assert '*2 中国*' in s
    assert '🏆' not in s


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

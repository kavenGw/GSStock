import calendar as _calmod
import logging
from datetime import date, datetime
from threading import Thread

from flask import render_template, request, jsonify, current_app

from app.routes import calendar_bp
from app.services.calendar_event import CalendarEventService

logger = logging.getLogger(__name__)

MAX_RANGE_DAYS = 200


def default_range(today: date = None) -> tuple[date, date]:
    """当月 1 号 ~ 下月末"""
    if today is None:
        today = date.today()

    start = date(today.year, today.month, 1)
    ey, em = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    end = date(ey, em, _calmod.monthrange(ey, em)[1])
    return start, end


def _parse(value: str):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


@calendar_bp.route('/')
def index():
    start, end = default_range()
    months = [
        {'year': start.year, 'month': start.month,
         'label': f'{start.year}年{start.month}月'},
        {'year': end.year, 'month': end.month,
         'label': f'{end.year}年{end.month}月'},
    ]
    return render_template('calendar.html', initial_months=months)


@calendar_bp.route('/api/events')
def get_events():
    d_start, d_end = default_range()
    start = _parse(request.args.get('start', '')) or d_start
    end = _parse(request.args.get('end', '')) or d_end

    if end < start:
        start, end = d_start, d_end
    if (end - start).days > MAX_RANGE_DAYS:
        return jsonify({'error': f'日期跨度不得超过 {MAX_RANGE_DAYS} 天'}), 400

    try:
        events = CalendarEventService.get_events(start, end)
        stale_hours = CalendarEventService.hours_since_refresh()
    except Exception as e:
        logger.warning(f'[事件日历] 读取失败: {e}')
        events, stale_hours = [], None

    return jsonify({
        'events': events,
        'start': start.isoformat(),
        'end': end.isoformat(),
        'stale_hours': stale_hours,
    })


@calendar_bp.route('/api/refresh', methods=['POST'])
def refresh():
    """异步触发采集"""
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            CalendarEventService.refresh_all()

    Thread(target=_run, daemon=True).start()
    return jsonify({'message': '正在刷新，请稍后刷新页面查看'}), 202

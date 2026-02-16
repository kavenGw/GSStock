"""美联储利率概率服务

从 CME FedWatch Tool 获取降息/加息概率数据
"""
import logging
import requests
from datetime import datetime, date, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# 美联储 FOMC 会议历史决议
# action: 'cut'=降息, 'hike'=加息, 'hold'=维持
# bps: 基点变化 (25=0.25%, 50=0.5%)
FOMC_DECISIONS = [
    # 2022 加息周期
    {'date': date(2022, 3, 16), 'action': 'hike', 'bps': 25, 'rate': 0.50},
    {'date': date(2022, 5, 4), 'action': 'hike', 'bps': 50, 'rate': 1.00},
    {'date': date(2022, 6, 15), 'action': 'hike', 'bps': 75, 'rate': 1.75},
    {'date': date(2022, 7, 27), 'action': 'hike', 'bps': 75, 'rate': 2.50},
    {'date': date(2022, 9, 21), 'action': 'hike', 'bps': 75, 'rate': 3.25},
    {'date': date(2022, 11, 2), 'action': 'hike', 'bps': 75, 'rate': 4.00},
    {'date': date(2022, 12, 14), 'action': 'hike', 'bps': 50, 'rate': 4.50},
    # 2023
    {'date': date(2023, 2, 1), 'action': 'hike', 'bps': 25, 'rate': 4.75},
    {'date': date(2023, 3, 22), 'action': 'hike', 'bps': 25, 'rate': 5.00},
    {'date': date(2023, 5, 3), 'action': 'hike', 'bps': 25, 'rate': 5.25},
    {'date': date(2023, 6, 14), 'action': 'hold', 'bps': 0, 'rate': 5.25},
    {'date': date(2023, 7, 26), 'action': 'hike', 'bps': 25, 'rate': 5.50},
    {'date': date(2023, 9, 20), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2023, 11, 1), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2023, 12, 13), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    # 2024
    {'date': date(2024, 1, 31), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2024, 3, 20), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2024, 5, 1), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2024, 6, 12), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2024, 7, 31), 'action': 'hold', 'bps': 0, 'rate': 5.50},
    {'date': date(2024, 9, 18), 'action': 'cut', 'bps': 50, 'rate': 5.00},
    {'date': date(2024, 11, 7), 'action': 'cut', 'bps': 25, 'rate': 4.75},
    {'date': date(2024, 12, 18), 'action': 'cut', 'bps': 25, 'rate': 4.50},
    # 2025
    {'date': date(2025, 1, 29), 'action': 'hold', 'bps': 0, 'rate': 4.50},
    {'date': date(2025, 3, 19), 'action': 'hold', 'bps': 0, 'rate': 4.50},
    {'date': date(2025, 5, 7), 'action': 'hold', 'bps': 0, 'rate': 4.50},
    {'date': date(2025, 6, 18), 'action': 'cut', 'bps': 25, 'rate': 4.25},
    {'date': date(2025, 7, 30), 'action': 'hold', 'bps': 0, 'rate': 4.25},
    {'date': date(2025, 9, 17), 'action': 'cut', 'bps': 25, 'rate': 4.00},
    {'date': date(2025, 11, 5), 'action': 'hold', 'bps': 0, 'rate': 4.00},
    {'date': date(2025, 12, 17), 'action': 'cut', 'bps': 25, 'rate': 3.75},
    # 2026
    {'date': date(2026, 1, 28), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 3, 18), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 4, 29), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 6, 17), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 7, 29), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 9, 16), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 11, 4), 'action': None, 'bps': None, 'rate': None},
    {'date': date(2026, 12, 16), 'action': None, 'bps': None, 'rate': None},
]

# 从决议数据提取会议日期列表
FOMC_MEETINGS = [d['date'] for d in FOMC_DECISIONS]

# 每日降息概率历史数据 (手动维护)
# 格式: 'YYYY-MM-DD': {'cut': 降息概率, 'hold': 维持概率, 'hike': 加息概率}
DAILY_RATE_PROBABILITIES = {
    # 2024年12月 - 降息周期末期
    '2024-12-02': {'cut': 65, 'hold': 35, 'hike': 0},
    '2024-12-03': {'cut': 68, 'hold': 32, 'hike': 0},
    '2024-12-04': {'cut': 70, 'hold': 30, 'hike': 0},
    '2024-12-05': {'cut': 72, 'hold': 28, 'hike': 0},
    '2024-12-06': {'cut': 75, 'hold': 25, 'hike': 0},
    '2024-12-09': {'cut': 78, 'hold': 22, 'hike': 0},
    '2024-12-10': {'cut': 80, 'hold': 20, 'hike': 0},
    '2024-12-11': {'cut': 82, 'hold': 18, 'hike': 0},
    '2024-12-12': {'cut': 85, 'hold': 15, 'hike': 0},
    '2024-12-13': {'cut': 88, 'hold': 12, 'hike': 0},
    '2024-12-16': {'cut': 90, 'hold': 10, 'hike': 0},
    '2024-12-17': {'cut': 92, 'hold': 8, 'hike': 0},
    '2024-12-18': {'cut': 95, 'hold': 5, 'hike': 0},  # FOMC会议日
    '2024-12-19': {'cut': 15, 'hold': 85, 'hike': 0},  # 会议后重置
    '2024-12-20': {'cut': 12, 'hold': 88, 'hike': 0},
    '2024-12-23': {'cut': 10, 'hold': 90, 'hike': 0},
    '2024-12-24': {'cut': 8, 'hold': 92, 'hike': 0},
    '2024-12-26': {'cut': 8, 'hold': 92, 'hike': 0},
    '2024-12-27': {'cut': 7, 'hold': 93, 'hike': 0},
    # 2025年1月
    '2025-01-02': {'cut': 5, 'hold': 95, 'hike': 0},
    '2025-01-03': {'cut': 5, 'hold': 95, 'hike': 0},
    # ... 后续数据可继续添加
    # 2025年11-12月示例数据
    '2025-11-28': {'cut': 25, 'hold': 75, 'hike': 0},
    '2025-12-01': {'cut': 28, 'hold': 72, 'hike': 0},
    '2025-12-02': {'cut': 32, 'hold': 68, 'hike': 0},
    '2025-12-03': {'cut': 35, 'hold': 65, 'hike': 0},
    '2025-12-04': {'cut': 38, 'hold': 62, 'hike': 0},
    '2025-12-05': {'cut': 42, 'hold': 58, 'hike': 0},
    '2025-12-06': {'cut': 45, 'hold': 55, 'hike': 0},
    '2025-12-09': {'cut': 50, 'hold': 50, 'hike': 0},
    '2025-12-10': {'cut': 55, 'hold': 45, 'hike': 0},
    '2025-12-11': {'cut': 60, 'hold': 40, 'hike': 0},
    '2025-12-12': {'cut': 65, 'hold': 35, 'hike': 0},
    '2025-12-13': {'cut': 68, 'hold': 32, 'hike': 0},
    '2025-12-16': {'cut': 72, 'hold': 28, 'hike': 0},
    '2025-12-17': {'cut': 78, 'hold': 22, 'hike': 0},  # FOMC会议日
    '2025-12-18': {'cut': 10, 'hold': 90, 'hike': 0},  # 会议后重置
    '2025-12-19': {'cut': 8, 'hold': 92, 'hike': 0},
    '2025-12-22': {'cut': 6, 'hold': 94, 'hike': 0},
    '2025-12-23': {'cut': 5, 'hold': 95, 'hike': 0},
    '2025-12-24': {'cut': 5, 'hold': 95, 'hike': 0},
    '2025-12-26': {'cut': 5, 'hold': 95, 'hike': 0},
    '2025-12-27': {'cut': 5, 'hold': 95, 'hike': 0},
}


class FedRateService:
    """美联储利率概率服务"""

    # CME FedWatch API
    CME_API_URL = "https://www.cmegroup.com/services/fedFundsFuturesChartData"

    # 缓存
    _cache = None
    _cache_time = None
    _cache_ttl = 3600  # 1小时缓存

    @classmethod
    def get_rate_probabilities(cls, force_refresh: bool = False) -> Optional[dict]:
        """获取美联储利率概率

        Returns:
            {
                'current_rate': 4.50,
                'next_meeting': '2025-01-29',
                'is_meeting_today': False,
                'probabilities': {
                    'cut': 35.5,      # 降息概率
                    'hold': 60.2,     # 维持概率
                    'hike': 4.3       # 加息概率
                },
                'expected_change': -25,  # 预期变化(基点)，负数表示降息
                'updated_at': '2024-12-28 10:30:00'
            }
        """
        # 检查缓存
        now = datetime.now()
        if (not force_refresh and cls._cache and cls._cache_time and
                (now - cls._cache_time).seconds < cls._cache_ttl):
            return cls._cache

        try:
            result = cls._fetch_from_cme()
            if result:
                cls._cache = result
                cls._cache_time = now
                return result
        except Exception as e:
            logger.error(f"[美联储利率] 获取利率概率失败: {e}", exc_info=True)

        # 如果获取失败，返回缓存或模拟数据
        if cls._cache:
            return cls._cache
        return cls._get_fallback_data()

    @classmethod
    def _fetch_from_cme(cls) -> Optional[dict]:
        """从 CME API 获取数据"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Referer': 'https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html'
            }

            response = requests.get(cls.CME_API_URL, headers=headers, timeout=10)

            if response.status_code != 200:
                logger.warning(f"[美联储利率] CME API 返回状态码: {response.status_code}")
                return None

            data = response.json()
            return cls._parse_cme_data(data)

        except requests.RequestException as e:
            logger.warning(f"[美联储利率] 请求 CME API 失败: {e}")
            return None
        except Exception as e:
            logger.warning(f"[美联储利率] 解析 CME 数据失败: {e}")
            return None

    @classmethod
    def _parse_cme_data(cls, data: dict) -> Optional[dict]:
        """解析 CME API 返回的数据"""
        try:
            # CME API 返回的数据结构可能变化，这里做兼容处理
            if not data:
                return None

            # 获取当前利率区间 (如 4.25-4.50)
            current_rate = 4.50  # 默认值

            # 解析概率数据
            probabilities = {'cut': 0, 'hold': 0, 'hike': 0}

            # CME 数据格式处理
            if isinstance(data, list) and len(data) > 0:
                first_meeting = data[0]
                if 'probabilities' in first_meeting:
                    probs = first_meeting['probabilities']
                    for prob in probs:
                        rate = prob.get('rate', 0)
                        probability = prob.get('probability', 0)
                        if rate < current_rate:
                            probabilities['cut'] += probability
                        elif rate > current_rate:
                            probabilities['hike'] += probability
                        else:
                            probabilities['hold'] += probability

            # 获取下次会议日期
            next_meeting = cls._get_next_meeting()
            is_meeting_today = next_meeting == date.today()

            # 计算预期变化
            expected_change = 0
            if probabilities['cut'] > 50:
                expected_change = -25
            elif probabilities['hike'] > 50:
                expected_change = 25

            return {
                'current_rate': current_rate,
                'next_meeting': next_meeting.isoformat() if next_meeting else None,
                'is_meeting_today': is_meeting_today,
                'probabilities': probabilities,
                'expected_change': expected_change,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"[美联储利率] 解析 CME 数据异常: {e}", exc_info=True)
            return None

    @classmethod
    def _get_next_meeting(cls) -> Optional[date]:
        """获取下一次 FOMC 会议日期"""
        today = date.today()
        for meeting in FOMC_MEETINGS:
            if meeting >= today:
                return meeting
        return None

    @classmethod
    def _get_fallback_data(cls) -> dict:
        """获取备用数据（当 API 不可用时）"""
        next_meeting = cls._get_next_meeting()
        is_meeting_today = next_meeting == date.today() if next_meeting else False

        return {
            'current_rate': 4.50,
            'next_meeting': next_meeting.isoformat() if next_meeting else None,
            'is_meeting_today': is_meeting_today,
            'probabilities': {
                'cut': 0,
                'hold': 100,
                'hike': 0
            },
            'expected_change': 0,
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'fallback': True
        }

    @classmethod
    def is_fomc_meeting_date(cls, check_date: date = None) -> bool:
        """检查指定日期是否是 FOMC 会议日"""
        if check_date is None:
            check_date = date.today()
        return check_date in FOMC_MEETINGS

    @classmethod
    def get_recent_meetings(cls, count: int = 3) -> list[dict]:
        """获取最近的 FOMC 会议日期

        Args:
            count: 返回的会议数量

        Returns:
            [{'date': '2025-01-29', 'is_past': False, 'is_today': False}, ...]
        """
        today = date.today()
        result = []

        for meeting in FOMC_MEETINGS:
            if meeting >= today - timedelta(days=30):  # 包含过去30天
                result.append({
                    'date': meeting.isoformat(),
                    'is_past': meeting < today,
                    'is_today': meeting == today
                })
                if len(result) >= count:
                    break

        return result

    @classmethod
    def get_decisions_in_range(cls, start_date: str, end_date: str) -> list[dict]:
        """获取指定日期范围内的 FOMC 决议

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            [{
                'date': '2024-09-18',
                'action': 'cut',      # cut/hike/hold/None
                'bps': 50,            # 基点
                'rate': 5.00,         # 决议后利率
                'label': '降息50bp'   # 显示标签
            }, ...]
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return []

        result = []
        action_labels = {
            'cut': '降息',
            'hike': '加息',
            'hold': '维持'
        }

        for decision in FOMC_DECISIONS:
            d = decision['date']
            if start <= d <= end:
                action = decision['action']
                bps = decision['bps']

                # 生成标签
                if action is None:
                    label = 'FOMC'
                elif action == 'hold':
                    label = '维持'
                else:
                    label = f"{action_labels.get(action, action)}{bps}bp"

                result.append({
                    'date': d.isoformat(),
                    'action': action,
                    'bps': bps,
                    'rate': decision['rate'],
                    'label': label
                })

        return result

    @classmethod
    def get_probabilities_in_range(cls, start_date: str, end_date: str) -> list[dict]:
        """获取指定日期范围内的每日降息概率

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            [{
                'date': '2024-12-01',
                'cut': 65,       # 降息概率
                'hold': 35,      # 维持概率
                'hike': 0        # 加息概率
            }, ...]
        """
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return []

        result = []
        current = start
        while current <= end:
            date_str = current.isoformat()
            if date_str in DAILY_RATE_PROBABILITIES:
                probs = DAILY_RATE_PROBABILITIES[date_str]
                result.append({
                    'date': date_str,
                    'cut': probs.get('cut', 0),
                    'hold': probs.get('hold', 0),
                    'hike': probs.get('hike', 0)
                })
            current += timedelta(days=1)

        return result

"""TD Sequential（九转序列）信号计算"""
import logging

logger = logging.getLogger(__name__)


class TDSequentialService:

    @staticmethod
    def calculate(ohlc_data: list) -> dict:
        if not ohlc_data or len(ohlc_data) < 5:
            return {'direction': None, 'count': 0, 'completed': False, 'history': []}

        closes = []
        time_keys = []
        for d in ohlc_data:
            close = d.get('close') or d.get('price') or 0
            if close <= 0:
                continue
            closes.append(close)
            time_keys.append(d.get('time') or d.get('date', ''))

        if len(closes) < 5:
            return {'direction': None, 'count': 0, 'completed': False, 'history': []}

        history = []
        buy_count = 0
        sell_count = 0

        for i in range(4, len(closes)):
            compare = closes[i - 4]

            if closes[i] < compare:
                buy_count += 1
                sell_count = 0
                direction = 'buy'
                count = buy_count
            elif closes[i] > compare:
                sell_count += 1
                buy_count = 0
                direction = 'sell'
                count = sell_count
            else:
                buy_count = 0
                sell_count = 0
                direction = None
                count = 0

            if count > 0:
                entry = {
                    'direction': direction,
                    'count': min(count, 9),
                    'price': closes[i],
                }
                tk = time_keys[i]
                if ':' in str(tk):
                    entry['time'] = tk
                else:
                    entry['date'] = tk
                history.append(entry)

            if buy_count >= 9:
                buy_count = 0
            if sell_count >= 9:
                sell_count = 0

        current_direction = None
        current_count = 0
        completed = False

        if history:
            last = history[-1]
            current_direction = last['direction']
            current_count = last['count']
            completed = current_count == 9

        return {
            'direction': current_direction,
            'count': current_count,
            'completed': completed,
            'history': history[-20:],
        }

"""DRAM 现货价格服务

爬取 TrendForce DRAM Spot Price 页面，解析 DDR5/DDR4 价格数据。
数据源：https://www.trendforce.com/price/dram/dram_spot
"""
import re
import logging
from datetime import date, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

from app import db
from app.models.dram_price import DramPrice

logger = logging.getLogger(__name__)

DRAM_SPECS = {
    'DDR5_16Gb': {
        'label': 'DDR5 16Gb',
        'pattern': r'DDR5\s+16Gb.*?(?:4800|5600)',
    },
    'DDR4_8Gb': {
        'label': 'DDR4 8Gb',
        'pattern': r'DDR4\s+8Gb.*?3200',
    },
    'DDR4_16Gb': {
        'label': 'DDR4 16Gb',
        'pattern': r'DDR4\s+16Gb.*?3200',
    },
}

TRENDFORCE_URL = 'https://www.trendforce.com/price/dram/dram_spot'
REQUEST_TIMEOUT = 15


class DramPriceService:
    """DRAM 现货价格服务"""

    _today_cache = None  # (date, data) 当天永久缓存

    @classmethod
    def get_dram_data(cls) -> dict:
        """获取 DRAM 价格数据（当天永久缓存）"""
        today = date.today()

        if cls._today_cache and cls._today_cache[0] == today:
            return cls._today_cache[1]

        today_prices = DramPrice.query.filter_by(date=today).all()
        if not today_prices:
            cls._fetch_and_save(today)
            today_prices = DramPrice.query.filter_by(date=today).all()

        today_data = []
        for spec_key, spec_info in DRAM_SPECS.items():
            record = next((p for p in today_prices if p.spec == spec_key), None)
            today_data.append({
                'spec': spec_key,
                'label': spec_info['label'],
                'avg_price': record.avg_price if record else None,
                'high_price': record.high_price if record else None,
                'low_price': record.low_price if record else None,
                'change_pct': record.change_pct if record else None,
            })

        history = cls._get_history(30)

        result = {'today': today_data, 'history': history}

        if any(d['avg_price'] is not None for d in today_data):
            cls._today_cache = (today, result)

        return result

    @classmethod
    def _fetch_and_save(cls, target_date: date) -> None:
        """爬取 TrendForce 页面并保存价格数据"""
        try:
            prices = cls._scrape_trendforce()
            if not prices:
                logger.warning("[DRAM] TrendForce 爬取无数据")
                return

            for spec_key, price_data in prices.items():
                existing = DramPrice.query.filter_by(
                    date=target_date, spec=spec_key
                ).first()
                if existing:
                    existing.avg_price = price_data['avg_price']
                    existing.high_price = price_data.get('high_price')
                    existing.low_price = price_data.get('low_price')
                    existing.change_pct = price_data.get('change_pct')
                else:
                    record = DramPrice(
                        date=target_date,
                        spec=spec_key,
                        avg_price=price_data['avg_price'],
                        high_price=price_data.get('high_price'),
                        low_price=price_data.get('low_price'),
                        change_pct=price_data.get('change_pct'),
                    )
                    db.session.add(record)
            db.session.commit()
            logger.info(f"[DRAM] 保存 {len(prices)} 条价格数据")
        except Exception as e:
            logger.error(f"[DRAM] 爬取保存失败: {e}", exc_info=True)
            db.session.rollback()

    @classmethod
    def _scrape_trendforce(cls) -> dict:
        """爬取 TrendForce DRAM Spot Price 页面"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            resp = requests.get(TRENDFORCE_URL, headers=headers, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f"[DRAM] 请求 TrendForce 失败: {e}")
            return {}

        soup = BeautifulSoup(resp.text, 'html.parser')
        results = {}

        rows = soup.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 6:
                continue

            row_text = cells[0].get_text(strip=True)

            for spec_key, spec_info in DRAM_SPECS.items():
                if spec_key in results:
                    continue
                if re.search(spec_info['pattern'], row_text, re.IGNORECASE):
                    try:
                        # 列结构：名称[0] | 盘高[1] | 盘低[2] | 前高[3] | 前低[4] | 盘均[5] | 涨跌幅[6]
                        high = cls._parse_price(cells[1].get_text(strip=True))
                        low = cls._parse_price(cells[2].get_text(strip=True))
                        avg = cls._parse_price(cells[5].get_text(strip=True))
                        change_pct = cls._parse_change(cells[6].get_text(strip=True)) if len(cells) > 6 else None

                        if avg is not None:
                            results[spec_key] = {
                                'avg_price': avg,
                                'high_price': high,
                                'low_price': low,
                                'change_pct': change_pct,
                            }
                            logger.info(f"[DRAM] 解析 {spec_key}: avg=${avg}, change={change_pct}%")
                    except Exception as e:
                        logger.warning(f"[DRAM] 解析 {spec_key} 行失败: {e}")

        return results

    @staticmethod
    def _parse_price(text: str) -> Optional[float]:
        """解析价格文本，提取数字"""
        match = re.search(r'[\d.]+', text.replace(',', ''))
        return float(match.group()) if match else None

    @staticmethod
    def _parse_change(text: str) -> Optional[float]:
        """解析涨跌幅文本"""
        match = re.search(r'[▲▼+-]?\s*([\d.]+)\s*%', text)
        if not match:
            return None
        value = float(match.group(1))
        if '▼' in text or '-' in text:
            value = -value
        return value

    @classmethod
    def _get_history(cls, days: int = 30) -> list:
        """获取最近N天的历史价格"""
        since = date.today() - timedelta(days=days)
        records = DramPrice.query.filter(
            DramPrice.date >= since
        ).order_by(DramPrice.date.asc()).all()

        date_map = {}
        for r in records:
            d = r.date.isoformat()
            if d not in date_map:
                date_map[d] = {'date': d}
            date_map[d][r.spec] = r.avg_price

        return list(date_map.values())

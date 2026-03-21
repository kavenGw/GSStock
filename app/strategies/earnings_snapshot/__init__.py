import logging
import re
from datetime import date, datetime, timedelta

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class EarningsSnapshotStrategy(Strategy):
    name = "earnings_snapshot"
    description = "每日财报估值快照预计算"
    schedule = "0 8 * * 1-5"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app import db
        from app.models.stock import Stock
        from app.models.earnings_snapshot import EarningsSnapshot
        from app.services.market_cap_service import MarketCapService
        from app.services.earnings_service import QuarterlyEarningsService
        from app.utils.market_identifier import MarketIdentifier

        today = date.today()
        all_stocks = Stock.query.all()
        codes = [s.stock_code for s in all_stocks if not MarketIdentifier.is_etf(s.stock_code)]
        stock_names = {s.stock_code: s.stock_name for s in all_stocks}

        logger.info(f"[财报快照] 开始计算 {len(codes)} 只股票")

        # 批量获取市值
        market_caps = MarketCapService.get_market_caps(codes)

        success_count = 0
        fail_count = 0

        # 季度标签格式转换: "Q3'25" → "2025Q3"
        def convert_label(label):
            m = re.match(r"Q(\d)'(\d{2})", label or '')
            if m:
                return f"20{m.group(2)}Q{m.group(1)}"
            return label

        for code in codes:
            try:
                cap = market_caps.get(code)
                earnings = QuarterlyEarningsService.get_earnings(code)

                if not earnings:
                    logger.debug(f"[财报快照] {code} 无财报数据，跳过")
                    fail_count += 1
                    continue

                # Q1=最近, Q4=最早（earnings已按时间倒序）
                q_data = []
                for i, e in enumerate(earnings[:4]):
                    q_data.append({
                        'revenue': e.get('revenue'),
                        'profit': e.get('profit'),
                        'label': convert_label(e.get('quarter')),
                    })
                # 补齐不足4个季度
                while len(q_data) < 4:
                    q_data.append({'revenue': None, 'profit': None, 'label': None})

                # 计算动态估值
                q1_profit = q_data[0]['profit']
                q1_revenue = q_data[0]['revenue']
                pe = None
                ps = None
                if cap and q1_profit and q1_profit > 0:
                    pe = round(cap / (q1_profit * 4), 1)
                if cap and q1_revenue and q1_revenue > 0:
                    ps = round(cap / (q1_revenue * 4), 1)

                # Upsert
                snapshot = EarningsSnapshot.query.filter_by(
                    stock_code=code, snapshot_date=today
                ).first()
                if not snapshot:
                    snapshot = EarningsSnapshot(stock_code=code, snapshot_date=today)
                    db.session.add(snapshot)

                snapshot.stock_name = stock_names.get(code, '')
                snapshot.market_cap = cap
                snapshot.q1_revenue = q_data[0]['revenue']
                snapshot.q2_revenue = q_data[1]['revenue']
                snapshot.q3_revenue = q_data[2]['revenue']
                snapshot.q4_revenue = q_data[3]['revenue']
                snapshot.q1_profit = q_data[0]['profit']
                snapshot.q2_profit = q_data[1]['profit']
                snapshot.q3_profit = q_data[2]['profit']
                snapshot.q4_profit = q_data[3]['profit']
                snapshot.q1_label = q_data[0]['label']
                snapshot.q2_label = q_data[1]['label']
                snapshot.q3_label = q_data[2]['label']
                snapshot.q4_label = q_data[3]['label']
                snapshot.pe_dynamic = pe
                snapshot.ps_dynamic = ps
                snapshot.updated_at = datetime.utcnow()

                db.session.commit()
                success_count += 1

            except Exception as e:
                db.session.rollback()
                logger.error(f"[财报快照] {code} 处理失败: {e}")
                fail_count += 1

        # 清理7天前的快照
        cutoff = today - timedelta(days=7)
        deleted = EarningsSnapshot.query.filter(
            EarningsSnapshot.snapshot_date < cutoff
        ).delete()
        db.session.commit()
        if deleted:
            logger.info(f"[财报快照] 清理 {deleted} 条过期快照")

        logger.info(f"[财报快照] 完成: 成功 {success_count}, 失败 {fail_count}")
        return [Signal(
            strategy=self.name,
            priority="LOW",
            title="财报快照更新完成",
            detail=f"成功 {success_count} 只, 失败 {fail_count} 只",
            data={'success': success_count, 'fail': fail_count}
        )]

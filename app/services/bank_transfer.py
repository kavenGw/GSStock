from datetime import date
from sqlalchemy import func, extract
from app import db
from app.models.bank_transfer import BankTransfer


class BankTransferService:
    @staticmethod
    def save_transfer(transfer_date: date, transfer_type: str, amount: float, note: str = None) -> BankTransfer:
        """保存转账记录"""
        transfer = BankTransfer(
            transfer_date=transfer_date,
            transfer_type=transfer_type,
            amount=amount,
            note=note
        )
        db.session.add(transfer)
        db.session.commit()
        return transfer

    @staticmethod
    def get_transfers(start_date: date = None, end_date: date = None) -> list:
        """获取转账列表"""
        query = BankTransfer.query
        if start_date:
            query = query.filter(BankTransfer.transfer_date >= start_date)
        if end_date:
            query = query.filter(BankTransfer.transfer_date <= end_date)
        return query.order_by(BankTransfer.transfer_date.desc()).all()

    @staticmethod
    def get_daily_transfer(target_date: date) -> dict:
        """获取指定日期转账汇总"""
        transfers = BankTransfer.query.filter_by(transfer_date=target_date).all()
        transfer_in = sum(t.amount for t in transfers if t.transfer_type == 'in')
        transfer_out = sum(t.amount for t in transfers if t.transfer_type == 'out')
        return {
            'transfer_in': transfer_in,
            'transfer_out': transfer_out,
            'net_transfer': transfer_in - transfer_out,
            'transfers': [t.to_dict() for t in transfers]
        }

    @staticmethod
    def get_transfer_stats() -> dict:
        """获取统计数据"""
        all_transfers = BankTransfer.query.order_by(BankTransfer.transfer_date.asc()).all()

        total_in = sum(t.amount for t in all_transfers if t.transfer_type == 'in')
        total_out = sum(t.amount for t in all_transfers if t.transfer_type == 'out')

        monthly_data = {}
        for t in all_transfers:
            month_key = t.transfer_date.strftime('%Y-%m')
            if month_key not in monthly_data:
                monthly_data[month_key] = {'in': 0, 'out': 0}
            if t.transfer_type == 'in':
                monthly_data[month_key]['in'] += t.amount
            else:
                monthly_data[month_key]['out'] += t.amount

        monthly_trend = [
            {
                'month': month,
                'transfer_in': round(data['in'], 2),
                'transfer_out': round(data['out'], 2),
                'net': round(data['in'] - data['out'], 2)
            }
            for month, data in sorted(monthly_data.items())
        ]

        return {
            'total_in': round(total_in, 2),
            'total_out': round(total_out, 2),
            'net_flow': round(total_in - total_out, 2),
            'monthly_trend': monthly_trend,
            'count': len(all_transfers)
        }

    @staticmethod
    def delete_transfer(transfer_id: int) -> bool:
        """删除转账记录"""
        transfer = BankTransfer.query.get(transfer_id)
        if transfer:
            db.session.delete(transfer)
            db.session.commit()
            return True
        return False

    @staticmethod
    def update_transfer(transfer_id: int, data: dict) -> BankTransfer | None:
        """更新转账记录"""
        transfer = BankTransfer.query.get(transfer_id)
        if not transfer:
            return None

        if 'transfer_date' in data:
            transfer.transfer_date = date.fromisoformat(data['transfer_date'])
        if 'transfer_type' in data:
            transfer.transfer_type = data['transfer_type']
        if 'amount' in data:
            transfer.amount = data['amount']
        if 'note' in data:
            transfer.note = data['note']

        db.session.commit()
        return transfer

    @staticmethod
    def get_transfer_by_id(transfer_id: int) -> BankTransfer | None:
        """根据ID获取转账记录"""
        return BankTransfer.query.get(transfer_id)

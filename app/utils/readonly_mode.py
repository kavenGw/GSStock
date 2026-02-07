"""只读模式工具

只读模式下：
- 不从外部服务器获取数据（akshare, yfinance 等）
- 不修改 stock.db（共享数据库）
- 可以修改 private.db（用户私有数据）
"""
from flask import current_app


def is_readonly_mode() -> bool:
    """检查是否处于只读模式"""
    try:
        return current_app.config.get('READONLY_MODE', False)
    except RuntimeError:
        # 应用上下文不存在时返回 False
        return False


def get_readonly_status() -> dict:
    """获取只读模式状态信息"""
    readonly = is_readonly_mode()
    return {
        'readonly': readonly,
        'message': '只读模式：仅使用缓存数据' if readonly else '',
        'can_fetch': not readonly,
        'can_modify_stock_db': not readonly,
        'can_modify_private_db': True  # 私有数据库始终可写
    }

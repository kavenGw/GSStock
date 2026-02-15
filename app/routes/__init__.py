from flask import Blueprint

main_bp = Blueprint('main', __name__)
position_bp = Blueprint('position', __name__, url_prefix='/positions')
advice_bp = Blueprint('advice', __name__, url_prefix='/advices')
category_bp = Blueprint('category', __name__, url_prefix='/categories')
trade_bp = Blueprint('trade', __name__, url_prefix='/trades')
wyckoff_bp = Blueprint('wyckoff', __name__, url_prefix='/wyckoff')
stock_bp = Blueprint('stock', __name__, url_prefix='/stocks')
daily_record_bp = Blueprint('daily_record', __name__, url_prefix='/daily-record')
profit_bp = Blueprint('profit', __name__, url_prefix='/profit')
rebalance_bp = Blueprint('rebalance', __name__, url_prefix='/rebalance')
heavy_metals_bp = Blueprint('heavy_metals', __name__, url_prefix='/heavy-metals')
preload_bp = Blueprint('preload', __name__)
alert_bp = Blueprint('alert', __name__, url_prefix='/alert')
briefing_bp = Blueprint('briefing', __name__, url_prefix='/briefing')
strategy_bp = Blueprint('strategy', __name__, url_prefix='/strategies')
stock_detail_bp = Blueprint('stock_detail', __name__, url_prefix='/api/stock-detail')

from app.routes import main, position, advice, category, trade, wyckoff, stock, daily_record, profit, rebalance, heavy_metals, preload, alert, briefing, strategy, stock_detail

import re
from app import db
from app.models.stock import Stock
from app.models.stock_alias import StockAlias
from app.models.category import StockCategory


class StockService:
    @staticmethod
    def _validate_stock_code(code):
        """验证股票代码格式，支持多市场"""
        if not code:
            return False
        # A股: 6位数字
        # 美股: 1-5位字母
        # 港股: 5位数字+.HK
        # 台股: 4位数字+.TW
        # 韩股: 6位数字+.KS
        patterns = [
            r'^\d{6}$',           # A股
            r'^[A-Z]{1,5}$',      # 美股
            r'^\d{5}\.HK$',       # 港股
            r'^\d{4}\.TW$',       # 台股
            r'^\d{6}\.KS$',       # 韩股
            r'^[0-9A-Z]{3,4}\.T$',  # 日股
        ]
        return any(re.match(pattern, code, re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def get_all_stocks():
        """获取所有股票"""
        return Stock.query.order_by(Stock.stock_code).all()

    @staticmethod
    def get_stock(code):
        """获取单个股票"""
        return Stock.query.get(code)

    @staticmethod
    def create_stock(code, name):
        """创建股票，返回 (stock, error)"""
        code = code.strip() if code else ''
        name = name.strip() if name else ''

        # 支持多市场股票代码
        if not StockService._validate_stock_code(code):
            return None, '股票代码格式不正确'
        if not name:
            return None, '股票名称不能为空'
        if len(name) > 50:
            return None, '股票名称不能超过50个字符'

        existing = Stock.query.get(code)
        if existing:
            return None, '该股票代码已存在'

        stock = Stock(stock_code=code, stock_name=name)
        db.session.add(stock)
        db.session.commit()
        return stock, None

    @staticmethod
    def update_stock(code, name=None, investment_advice=None):
        """更新股票信息，返回 (stock, error)"""
        stock = Stock.query.get(code)
        if not stock:
            return None, '股票代码不存在'

        if name is not None:
            name = name.strip() if name else ''
            if not name:
                return None, '股票名称不能为空'
            if len(name) > 50:
                return None, '股票名称不能超过50个字符'
            stock.stock_name = name

        if investment_advice is not None:
            stock.investment_advice = investment_advice.strip() if investment_advice else None

        db.session.commit()
        return stock, None

    @staticmethod
    def delete_stock(code):
        """删除股票，返回 error 或 None"""
        stock = Stock.query.get(code)
        if not stock:
            return '股票代码不存在'

        StockCategory.query.filter_by(stock_code=code).delete()
        db.session.delete(stock)
        db.session.commit()
        return None

    @staticmethod
    def detect_conflicts(positions):
        """
        检测 OCR 识别结果与已存储股票名称的冲突
        注意：如果 new_name 是该股票的别名，不报冲突

        Args:
            positions: OCR 结果列表，每项含 stock_code, stock_name

        Returns:
            冲突列表，每项含 code, old_name, new_name
        """
        if not positions:
            return []

        codes = [p.get('stock_code') for p in positions if p.get('stock_code')]
        if not codes:
            return []

        existing = {s.stock_code: s.stock_name for s in Stock.query.filter(Stock.stock_code.in_(codes)).all()}

        # 获取相关股票的所有别名
        aliases = StockAlias.query.filter(StockAlias.stock_code.in_(codes)).all()
        alias_map = {}
        for a in aliases:
            if a.stock_code not in alias_map:
                alias_map[a.stock_code] = set()
            alias_map[a.stock_code].add(a.alias_name)

        conflicts = []
        for p in positions:
            code = p.get('stock_code')
            new_name = p.get('stock_name')
            if code in existing and existing[code] != new_name:
                # 如果 new_name 是该股票的别名，不报冲突
                if code in alias_map and new_name in alias_map[code]:
                    continue
                conflicts.append({
                    'code': code,
                    'old_name': existing[code],
                    'new_name': new_name
                })
        return conflicts

    @staticmethod
    def find_code_by_name(name):
        """根据股票名称查找股票代码"""
        if not name:
            return None
        stock = Stock.query.filter_by(stock_name=name).first()
        return stock.stock_code if stock else None

    @staticmethod
    def fill_missing_codes(positions):
        """为没有股票代码的持仓记录补全代码"""
        for p in positions:
            if not p.get('stock_code') and p.get('stock_name'):
                code = StockService.find_code_by_name(p['stock_name'])
                if code:
                    p['stock_code'] = code

    @staticmethod
    def save_from_positions(positions, overwrite=False):
        """
        从持仓数据保存股票代码

        Args:
            positions: 持仓列表，每项含 stock_code, stock_name
            overwrite: True=覆盖已存在的名称，False=仅添加新股票
        """
        if not positions:
            return

        for p in positions:
            code = p.get('stock_code')
            name = p.get('stock_name')
            if not code or not name:
                continue

            existing = Stock.query.get(code)
            if existing:
                if overwrite:
                    existing.stock_name = name
            else:
                db.session.add(Stock(stock_code=code, stock_name=name))

        db.session.commit()

    @staticmethod
    def get_aliases(stock_code):
        """获取股票的所有别名"""
        return StockAlias.query.filter_by(stock_code=stock_code).all()

    @staticmethod
    def get_all_aliases():
        """获取所有别名"""
        return StockAlias.query.order_by(StockAlias.stock_code).all()

    @staticmethod
    def create_alias(alias_name, stock_code):
        """创建股票别名，返回 (alias, error)"""
        alias_name = alias_name.strip() if alias_name else ''
        stock_code = stock_code.strip() if stock_code else ''

        if not alias_name:
            return None, '别名不能为空'
        if len(alias_name) > 50:
            return None, '别名不能超过50个字符'
        if not stock_code:
            return None, '股票代码不能为空'

        stock = Stock.query.get(stock_code)
        if not stock:
            return None, '股票代码不存在'

        existing = StockAlias.query.filter_by(alias_name=alias_name).first()
        if existing:
            return None, f'该别名已存在，映射到 {existing.stock_code}'

        alias = StockAlias(alias_name=alias_name, stock_code=stock_code)
        db.session.add(alias)
        db.session.commit()
        return alias, None

    @staticmethod
    def delete_alias(alias_id):
        """删除别名，返回 error 或 None"""
        alias = StockAlias.query.get(alias_id)
        if not alias:
            return '别名不存在'

        db.session.delete(alias)
        db.session.commit()
        return None

    @staticmethod
    def find_code_by_alias(name):
        """根据别名查找股票代码"""
        if not name:
            return None
        alias = StockAlias.query.filter_by(alias_name=name).first()
        return alias.stock_code if alias else None

    @staticmethod
    def generate_tags(stock_code, stock_name=None):
        """调用 LLM 为单个股票生成标签，返回 (tags_str, error)"""
        import json
        import re

        stock = Stock.query.get(stock_code)
        if not stock:
            return None, '股票代码不存在'

        name = stock_name or stock.stock_name

        from app.llm.router import llm_router
        from app.llm.prompts.stock_tags import TAGS_SYSTEM_PROMPT, build_tags_prompt

        provider = llm_router.route('stock_tags')
        if not provider:
            return None, 'LLM 不可用'

        try:
            response = provider.chat([
                {'role': 'system', 'content': TAGS_SYSTEM_PROMPT},
                {'role': 'user', 'content': build_tags_prompt(stock_code, name)},
            ], temperature=0.3, max_tokens=500)

            text = response.strip()
            m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if m:
                text = m.group(1).strip()

            tags_list = json.loads(text)
            if not isinstance(tags_list, list):
                return None, 'LLM 返回格式错误'

            tags_str = ','.join(str(t) for t in tags_list if t)
            stock.tags = tags_str
            db.session.commit()
            return tags_str, None
        except Exception as e:
            return None, f'标签生成失败: {e}'

    @staticmethod
    def batch_generate_tags(overwrite=False):
        """批量为股票生成标签，返回 {code: tags_str} 或 {code: error}"""
        import logging
        logger = logging.getLogger(__name__)

        stocks = Stock.query.all()
        results = {}

        for stock in stocks:
            if not overwrite and stock.tags:
                results[stock.stock_code] = stock.tags
                continue

            tags_str, error = StockService.generate_tags(stock.stock_code)
            if error:
                logger.warning(f'[标签生成] {stock.stock_code} 失败: {error}')
                results[stock.stock_code] = f'ERROR: {error}'
            else:
                results[stock.stock_code] = tags_str
                logger.info(f'[标签生成] {stock.stock_code}: {tags_str}')

        return results

    @staticmethod
    def update_tags(code, tags):
        """手动更新股票标签，返回 (stock, error)"""
        stock = Stock.query.get(code)
        if not stock:
            return None, '股票代码不存在'

        stock.tags = tags.strip() if tags else None
        db.session.commit()
        return stock, None

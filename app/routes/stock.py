from flask import request, jsonify, render_template
from app.routes import stock_bp
from app.services.stock import StockService
from app.services.category import CategoryService


@stock_bp.route('/manage')
def manage():
    """股票代码管理页面"""
    stocks = StockService.get_all_stocks()
    stock_codes = [s.stock_code for s in stocks]
    stock_categories = CategoryService.get_stock_categories_map(stock_codes)
    categories = CategoryService.get_category_tree()
    aliases = StockService.get_all_aliases()

    # 构建 stock_code -> [alias_name, ...] 映射
    alias_map = {}
    for alias in aliases:
        if alias.stock_code not in alias_map:
            alias_map[alias.stock_code] = []
        alias_map[alias.stock_code].append(alias.alias_name)

    # 按分类组织股票
    stocks_by_category = {}
    uncategorized_stocks = []
    stock_dict = {s.stock_code: s for s in stocks}

    # 初始化分类结构
    for parent in categories:
        stocks_by_category[parent['id']] = {
            'name': parent['name'],
            'stocks': [],
            'children': {}
        }
        for child in parent.get('children', []):
            stocks_by_category[parent['id']]['children'][child['id']] = {
                'name': child['name'],
                'stocks': []
            }

    # 分配股票到分类
    for stock in stocks:
        sc = stock_categories.get(stock.stock_code)
        if not sc:
            uncategorized_stocks.append(stock)
            continue

        cat_id = sc['category_id']
        parent_id = sc.get('parent_id')

        if parent_id:
            # 二级分类
            if parent_id in stocks_by_category:
                children = stocks_by_category[parent_id]['children']
                if cat_id in children:
                    children[cat_id]['stocks'].append(stock)
        else:
            # 一级分类
            if cat_id in stocks_by_category:
                stocks_by_category[cat_id]['stocks'].append(stock)

    return render_template('stock_manage.html',
                           stocks=stocks,
                           stocks_by_category=stocks_by_category,
                           uncategorized_stocks=uncategorized_stocks,
                           stock_categories=stock_categories,
                           categories=categories,
                           alias_map=alias_map)


@stock_bp.route('', methods=['GET'])
def get_all():
    """获取所有股票"""
    stocks = StockService.get_all_stocks()
    return jsonify({'stocks': [s.to_dict() for s in stocks]})


@stock_bp.route('', methods=['POST'])
def create():
    """创建股票"""
    data = request.get_json()
    code = data.get('stock_code', '') if data else ''
    name = data.get('stock_name', '') if data else ''
    stock, error = StockService.create_stock(code, name)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(stock.to_dict()), 201


@stock_bp.route('/<code>', methods=['PUT'])
def update(code):
    """更新股票信息"""
    data = request.get_json() or {}
    name = data.get('stock_name')
    investment_advice = data.get('investment_advice')

    stock, error = StockService.update_stock(code, name=name, investment_advice=investment_advice)
    if error:
        status = 404 if '不存在' in error else 400
        return jsonify({'error': error}), status
    return jsonify(stock.to_dict())


@stock_bp.route('/<code>', methods=['DELETE'])
def delete(code):
    """删除股票"""
    error = StockService.delete_stock(code)
    if error:
        return jsonify({'error': error}), 404
    return jsonify({'message': '删除成功'})


@stock_bp.route('/aliases', methods=['GET'])
def get_all_aliases():
    """获取所有别名"""
    aliases = StockService.get_all_aliases()
    return jsonify({'aliases': [a.to_dict() for a in aliases]})


@stock_bp.route('/aliases', methods=['POST'])
def create_alias():
    """创建别名"""
    data = request.get_json()
    alias_name = data.get('alias_name', '') if data else ''
    stock_code = data.get('stock_code', '') if data else ''
    alias, error = StockService.create_alias(alias_name, stock_code)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(alias.to_dict()), 201


@stock_bp.route('/aliases/<int:alias_id>', methods=['DELETE'])
def delete_alias(alias_id):
    """删除别名"""
    error = StockService.delete_alias(alias_id)
    if error:
        return jsonify({'error': error}), 404
    return jsonify({'message': '删除成功'})


@stock_bp.route('/<code>/aliases', methods=['PUT'])
def update_aliases(code):
    """批量更新股票的别名"""
    data = request.get_json()
    aliases_input = data.get('aliases', []) if data else []

    # 验证股票存在
    stock = StockService.get_stock(code)
    if not stock:
        return jsonify({'error': '股票代码不存在'}), 404

    # 处理输入：去除空格，过滤空值
    new_aliases = []
    for alias in aliases_input:
        alias = alias.strip() if alias else ''
        if alias:
            new_aliases.append(alias)

    # 检查别名是否已被其他股票使用
    from app.models.stock_alias import StockAlias
    for alias_name in new_aliases:
        existing = StockAlias.query.filter_by(alias_name=alias_name).first()
        if existing and existing.stock_code != code:
            return jsonify({'error': f'别名 "{alias_name}" 已被 {existing.stock_code} 使用'}), 400

    # 删除旧别名
    current_aliases = StockService.get_aliases(code)
    for alias in current_aliases:
        StockService.delete_alias(alias.id)

    # 创建新别名
    created_aliases = []
    for alias_name in new_aliases:
        alias, error = StockService.create_alias(alias_name, code)
        if alias:
            created_aliases.append(alias_name)

    return jsonify({'aliases': created_aliases})


@stock_bp.route('/api/advice', methods=['GET'])
def get_advice_batch():
    """批量获取股票投资建议"""
    from app.models.stock import Stock

    codes_str = request.args.get('codes', '')
    codes = [c.strip() for c in codes_str.split(',') if c.strip()]

    if not codes:
        return jsonify({})

    stocks = Stock.query.filter(Stock.stock_code.in_(codes)).all()
    result = {s.stock_code: s.investment_advice for s in stocks if s.investment_advice}
    return jsonify(result)

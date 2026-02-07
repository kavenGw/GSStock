from flask import request, jsonify, render_template
from app.routes import category_bp
from app.services.category import CategoryService


@category_bp.route('/manage')
def manage():
    """板块管理页面"""
    category_tree = CategoryService.get_category_tree()
    return render_template('category.html', category_tree=category_tree)


@category_bp.route('', methods=['GET'])
def get_all():
    """获取所有板块（扁平列表）"""
    categories = CategoryService.get_all_categories()
    return jsonify({'categories': [c.to_dict() for c in categories]})


@category_bp.route('/tree', methods=['GET'])
def get_tree():
    """获取板块树形结构"""
    return jsonify({'categories': CategoryService.get_category_tree()})


@category_bp.route('', methods=['POST'])
def create():
    """创建板块"""
    data = request.get_json()
    name = data.get('name', '') if data else ''
    parent_id = data.get('parent_id') if data else None
    category, error = CategoryService.create_category(name, parent_id)
    if error:
        return jsonify({'error': error}), 400
    return jsonify(category.to_dict())


@category_bp.route('/<int:category_id>', methods=['PUT'])
def update(category_id):
    """更新板块"""
    data = request.get_json()
    name = data.get('name', '') if data else ''
    category, error = CategoryService.update_category(category_id, name)
    if error:
        return jsonify({'error': error}), 400 if '不能' in error or '已存在' in error else 404
    return jsonify(category.to_dict())


@category_bp.route('/<int:category_id>', methods=['DELETE'])
def delete(category_id):
    """删除板块"""
    success, error = CategoryService.delete_category(category_id)
    if not success:
        return jsonify({'error': error}), 404
    return jsonify({'success': True})


@category_bp.route('/stock/<stock_code>', methods=['PUT'])
def set_stock_category(stock_code):
    """设置股票板块"""
    data = request.get_json()
    category_id = data.get('category_id') if data else None
    success = CategoryService.set_stock_category(stock_code, category_id)
    if not success:
        return jsonify({'error': '板块不存在'}), 404
    return jsonify({'success': True})


@category_bp.route('/<int:category_id>/description', methods=['PUT'])
def update_description(category_id):
    """更新板块资讯描述"""
    data = request.get_json()
    description = data.get('description', '') if data else ''
    category, error = CategoryService.update_description(category_id, description)
    if error:
        return jsonify({'error': error}), 404
    return jsonify(category.to_dict())

from app import db
from app.models.category import Category, StockCategory


class CategoryService:
    @staticmethod
    def get_all_categories():
        """获取所有板块（扁平列表）"""
        return Category.query.order_by(Category.parent_id.nullsfirst(), Category.name).all()

    @staticmethod
    def get_parent_categories():
        """获取所有一级板块"""
        return Category.query.filter_by(parent_id=None).order_by(Category.name).all()

    @staticmethod
    def get_category_tree():
        """获取板块树形结构"""
        parents = Category.query.filter_by(parent_id=None).order_by(Category.name).all()
        result = []
        for p in parents:
            item = p.to_dict()
            item['children'] = [c.to_dict() for c in sorted(p.children, key=lambda x: x.name)]
            result.append(item)
        return result

    @staticmethod
    def create_category(name, parent_id=None):
        """创建板块，返回 (category, error)"""
        name = name.strip() if name else ''
        if not name:
            return None, '板块名称不能为空'
        if len(name) > 20:
            return None, '板块名称不能超过20个字符'

        if parent_id:
            parent = Category.query.get(parent_id)
            if not parent:
                return None, '父板块不存在'
            if parent.parent_id:
                return None, '不支持三级板块'
            existing = Category.query.filter_by(name=name, parent_id=parent_id).first()
            if existing:
                return None, '同级板块名称已存在'
        else:
            existing = Category.query.filter_by(name=name, parent_id=None).first()
            if existing:
                return None, '一级板块名称已存在'

        category = Category(name=name, parent_id=parent_id)
        db.session.add(category)
        db.session.commit()
        return category, None

    @staticmethod
    def update_category(category_id, name):
        """更新板块名称，返回 (category, error)"""
        name = name.strip() if name else ''
        if not name:
            return None, '板块名称不能为空'
        if len(name) > 20:
            return None, '板块名称不能超过20个字符'

        category = Category.query.get(category_id)
        if not category:
            return None, '板块不存在'

        existing = Category.query.filter_by(name=name, parent_id=category.parent_id).first()
        if existing and existing.id != category_id:
            return None, '同级板块名称已存在'

        category.name = name
        db.session.commit()
        return category, None

    @staticmethod
    def delete_category(category_id):
        """删除板块（子板块级联删除，关联股票变为未设板块）"""
        category = Category.query.get(category_id)
        if not category:
            return False, '板块不存在'

        db.session.delete(category)
        db.session.commit()
        return True, None

    @staticmethod
    def set_stock_category(stock_code, category_id):
        """设置股票板块（category_id=None 清除板块）"""
        stock_cat = StockCategory.query.filter_by(stock_code=stock_code).first()

        if category_id is None:
            if stock_cat:
                db.session.delete(stock_cat)
                db.session.commit()
            return True

        if not Category.query.get(category_id):
            return False

        if stock_cat:
            stock_cat.category_id = category_id
        else:
            stock_cat = StockCategory(stock_code=stock_code, category_id=category_id)
            db.session.add(stock_cat)

        db.session.commit()
        return True

    @staticmethod
    def get_stock_categories_map(stock_codes=None):
        """获取股票板块映射 {stock_code: category_dict}，可选过滤指定股票"""
        query = StockCategory.query
        if stock_codes:
            query = query.filter(StockCategory.stock_code.in_(stock_codes))
        result = {}
        for sc in query.all():
            result[sc.stock_code] = sc.to_dict()
        return result

    @staticmethod
    def update_description(category_id, description):
        """更新板块资讯描述，返回 (category, error)"""
        category = Category.query.get(category_id)
        if not category:
            return None, '板块不存在'

        if description and len(description) > 2000:
            description = description[:2000]

        category.description = description
        db.session.commit()
        return category, None

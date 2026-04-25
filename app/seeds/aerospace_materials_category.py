"""航天特种材料板块 seed（幂等）

一级板块 "航天特种材料" + 二级板块（钛合金/高温合金/复合材料），
覆盖宝钛/西部材料/西部超导/抚顺特钢/光威复材等核心标的。

幂等规则（遵循 CLAUDE.md 铁律）：
- 板块：同名同父存在 → 复用 id
- Stock：存在 → 跳过，不覆盖 stock_name
- StockCategory：已归属任何分类 → 保留原分类（保护跨板块引用）
- investment_advice：已有非空值 → 不覆盖
"""
import logging

logger = logging.getLogger(__name__)

AEROSPACE_PARENT = '航天特种材料'
SUBCATEGORIES = ['钛合金', '高温合金', '复合材料']

AEROSPACE_STOCKS = [
    # 钛合金（航天结构件 / 核电 / 化工）
    {'code': '600456', 'name': '宝钛股份', 'sub': '钛合金', 'advice': ''},
    {'code': '002149', 'name': '西部材料', 'sub': '钛合金', 'advice': ''},
    {'code': '688122', 'name': '西部超导', 'sub': '钛合金', 'advice': ''},

    # 高温合金（航空发动机 / 燃气轮机）
    {'code': '600399', 'name': '抚顺特钢', 'sub': '高温合金', 'advice': ''},

    # 复合材料（碳纤维）
    {'code': '300699', 'name': '光威复材', 'sub': '复合材料', 'advice': ''},
]


def _get_or_create_category(name, parent_id=None):
    from app.models.category import Category
    from app import db

    existing = Category.query.filter_by(name=name, parent_id=parent_id).first()
    if existing:
        return existing, False

    category = Category(name=name, parent_id=parent_id)
    db.session.add(category)
    db.session.commit()
    return category, True


def seed_aerospace_materials_category():
    """幂等 seed：航天特种材料板块 + 股票 + 归属 + 可选投资建议。

    失败不抛出（启动不可被阻断），遵循 CLAUDE.md 铁律：
    已存在的 stock_name / investment_advice / StockCategory 归属一律不覆盖。
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import StockCategory

    try:
        parent, parent_created = _get_or_create_category(AEROSPACE_PARENT, parent_id=None)
        if parent_created:
            logger.info(f'[seed.aerospace] 创建一级板块 {AEROSPACE_PARENT} id={parent.id}')

        sub_map = {}
        for sub_name in SUBCATEGORIES:
            sub, created = _get_or_create_category(sub_name, parent_id=parent.id)
            sub_map[sub_name] = sub.id
            if created:
                logger.info(f'[seed.aerospace] 创建二级板块 {sub_name} id={sub.id}')

        added_stock = 0
        added_category = 0
        added_advice = 0
        skipped_category = 0

        for item in AEROSPACE_STOCKS:
            code = item['code']
            name = item['name']
            sub_name = item['sub']
            advice = item.get('advice', '')
            sub_id = sub_map.get(sub_name)
            if sub_id is None:
                logger.warning(f'[seed.aerospace] 子分类 {sub_name} 查找失败，跳过 {code}')
                continue

            stock = Stock.query.get(code)
            if not stock:
                stock = Stock(stock_code=code, stock_name=name)
                db.session.add(stock)
                db.session.flush()
                added_stock += 1

            sc = StockCategory.query.filter_by(stock_code=code).first()
            if not sc:
                db.session.add(StockCategory(stock_code=code, category_id=sub_id))
                added_category += 1
            elif sc.category_id != sub_id:
                skipped_category += 1
                logger.debug(f'[seed.aerospace] {code} 已归属 category_id={sc.category_id}，保留不动')

            if advice and not (stock.investment_advice or '').strip():
                stock.investment_advice = advice
                added_advice += 1

        db.session.commit()

        if added_stock or added_category or added_advice or parent_created:
            logger.info(
                f'[seed.aerospace] 完成 新增股票={added_stock} 新增归属={added_category} '
                f'写入建议={added_advice} 保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.aerospace] 执行失败（忽略，不阻断启动）: {exc}')

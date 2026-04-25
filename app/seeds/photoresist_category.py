"""光刻胶产业链板块 seed（幂等）

一级板块 "光刻胶产业链" + 二级板块（半导体光刻胶/面板光刻胶/PCB 光刻胶/
光刻胶单体/光引发剂/电子特气），覆盖 supply_chain 'photoresist' 图谱中的
A 股核心标的。已归属其他板块的标的（300398 飞凯/300576 容大/002463 沪电/
002938 鹏鼎/002384 东山/000725 京东方/000100 TCL/002409 雅克/688981 中芯）
受 seed 铁律保护，不会改变其原归属，仅在产业链图谱 role 中标注关联。

幂等规则（遵循 CLAUDE.md 铁律）：
- 板块：同名同父存在 → 复用 id
- Stock：存在 → 跳过，不覆盖 stock_name
- StockCategory：已归属任何分类 → 保留原分类
- investment_advice：已有非空值 → 不覆盖
"""
import logging

logger = logging.getLogger(__name__)

PHOTORESIST_PARENT = '光刻胶产业链'
SUBCATEGORIES = [
    '半导体光刻胶', '面板光刻胶', 'PCB 光刻胶',
    '光刻胶单体', '光引发剂', '电子特气',
]

PHOTORESIST_STOCKS = [
    # 半导体光刻胶（KrF/ArF/EUV）
    {'code': '603650', 'name': '彤程新材', 'sub': '半导体光刻胶'},
    {'code': '300346', 'name': '南大光电', 'sub': '半导体光刻胶'},
    {'code': '603306', 'name': '华懋科技', 'sub': '半导体光刻胶'},
    {'code': '300236', 'name': '上海新阳', 'sub': '半导体光刻胶'},
    {'code': '300655', 'name': '晶瑞电材', 'sub': '半导体光刻胶'},

    # 面板光刻胶（LCD/OLED）— 飞凯 300398/容大 300576 已在他板块，铁律保护
    {'code': '300398', 'name': '飞凯材料', 'sub': '面板光刻胶'},
    {'code': '300576', 'name': '容大感光', 'sub': '面板光刻胶'},

    # PCB 光刻胶（干膜/湿膜/阻焊油墨）
    {'code': '300537', 'name': '广信材料', 'sub': 'PCB 光刻胶'},

    # 光刻胶单体/树脂
    {'code': '688550', 'name': '瑞联新材', 'sub': '光刻胶单体'},
    {'code': '002326', 'name': '永太科技', 'sub': '光刻胶单体'},

    # 光引发剂
    {'code': '300429', 'name': '强力新材', 'sub': '光引发剂'},

    # 电子特气（南大光电跨链，002409 雅克已在 storage 链）
    {'code': '688268', 'name': '华特气体', 'sub': '电子特气'},
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


def seed_photoresist_category():
    """幂等 seed：光刻胶产业链板块 + 股票 + 归属。

    失败不抛出（启动不可被阻断），遵循 CLAUDE.md 铁律：
    已存在的 stock_name / investment_advice / StockCategory 归属一律不覆盖。
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import StockCategory

    try:
        parent, parent_created = _get_or_create_category(PHOTORESIST_PARENT, parent_id=None)
        if parent_created:
            logger.info(f'[seed.photoresist] 创建一级板块 {PHOTORESIST_PARENT} id={parent.id}')

        sub_map = {}
        for sub_name in SUBCATEGORIES:
            sub, created = _get_or_create_category(sub_name, parent_id=parent.id)
            sub_map[sub_name] = sub.id
            if created:
                logger.info(f'[seed.photoresist] 创建二级板块 {sub_name} id={sub.id}')

        added_stock = 0
        added_category = 0
        skipped_category = 0

        for item in PHOTORESIST_STOCKS:
            code = item['code']
            name = item['name']
            sub_name = item['sub']
            sub_id = sub_map.get(sub_name)
            if sub_id is None:
                logger.warning(f'[seed.photoresist] 子分类 {sub_name} 查找失败，跳过 {code}')
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
                logger.debug(f'[seed.photoresist] {code} 已归属 category_id={sc.category_id}，保留不动')

        db.session.commit()

        if added_stock or added_category or parent_created:
            logger.info(
                f'[seed.photoresist] 完成 新增股票={added_stock} 新增归属={added_category} '
                f'保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.photoresist] 执行失败（忽略，不阻断启动）: {exc}')

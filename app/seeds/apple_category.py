"""苹果产业链板块 seed（幂等）

一级板块 "苹果产业链" + 二级板块（玻璃外观件/光学摄像/PCB-FPC/声学/
连接结构件/电池电源/显示面板/天线无线充/整机组装），覆盖 supply_chain 'apple'
图谱中的 A 股核心标的。港股标的（瑞声/舜宇/丘钛/比亚迪电子）不在本 seed。

幂等规则（遵循 CLAUDE.md 铁律）：
- 板块：同名同父存在 → 复用 id
- Stock：存在 → 跳过，不覆盖 stock_name
- StockCategory：已归属任何分类 → 保留原分类（保护跨板块引用，
  如 002938/002463 已在 PCB 链、601138 已在 CPU 链）
- investment_advice：已有非空值 → 不覆盖
"""
import logging

logger = logging.getLogger(__name__)

APPLE_PARENT = '苹果产业链'
SUBCATEGORIES = [
    '玻璃外观件', '光学摄像', 'PCB / FPC', '声学元件',
    '连接结构件', '电池电源', '显示面板', '天线 / 无线充电', '整机组装',
]

APPLE_STOCKS = [
    # 玻璃盖板与外观件
    {'code': '300433', 'name': '蓝思科技',   'sub': '玻璃外观件'},
    {'code': '300088', 'name': '长信科技',   'sub': '玻璃外观件'},
    {'code': '603876', 'name': '鼎胜新材',   'sub': '玻璃外观件'},

    # 光学摄像头
    {'code': '002456', 'name': '欧菲光',     'sub': '光学摄像'},
    {'code': '600703', 'name': '三安光电',   'sub': '光学摄像'},

    # PCB / FPC（002938/002463 已在 PCB 分类，受 seed 铁律保护）
    {'code': '002938', 'name': '鹏鼎控股',   'sub': 'PCB / FPC'},
    {'code': '002384', 'name': '东山精密',   'sub': 'PCB / FPC'},
    {'code': '002463', 'name': '沪电股份',   'sub': 'PCB / FPC'},

    # 声学元件（瑞声 2018.HK 港股不入 seed）
    {'code': '002241', 'name': '歌尔股份',   'sub': '声学元件'},

    # 连接器与精密结构件
    {'code': '002475', 'name': '立讯精密',   'sub': '连接结构件'},
    {'code': '300115', 'name': '长盈精密',   'sub': '连接结构件'},
    {'code': '002635', 'name': '安洁科技',   'sub': '连接结构件'},

    # 电池与电源
    {'code': '000049', 'name': '德赛电池',   'sub': '电池电源'},
    {'code': '300207', 'name': '欣旺达',     'sub': '电池电源'},

    # 显示面板
    {'code': '000725', 'name': '京东方A',    'sub': '显示面板'},
    {'code': '000100', 'name': 'TCL科技',    'sub': '显示面板'},

    # 天线 / 无线充电模组
    {'code': '300136', 'name': '信维通信',   'sub': '天线 / 无线充电'},

    # 整机组装（601138 已在 CPU 链；002475/002241 已在上游，仅幂等补 stock_name）
    {'code': '601138', 'name': '工业富联',   'sub': '整机组装'},
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


def seed_apple_category():
    """幂等 seed：苹果产业链板块 + 股票 + 归属。

    失败不抛出（启动不可被阻断），遵循 CLAUDE.md 铁律：
    已存在的 stock_name / investment_advice / StockCategory 归属一律不覆盖。
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import StockCategory

    try:
        parent, parent_created = _get_or_create_category(APPLE_PARENT, parent_id=None)
        if parent_created:
            logger.info(f'[seed.apple] 创建一级板块 {APPLE_PARENT} id={parent.id}')

        sub_map = {}
        for sub_name in SUBCATEGORIES:
            sub, created = _get_or_create_category(sub_name, parent_id=parent.id)
            sub_map[sub_name] = sub.id
            if created:
                logger.info(f'[seed.apple] 创建二级板块 {sub_name} id={sub.id}')

        added_stock = 0
        added_category = 0
        skipped_category = 0

        for item in APPLE_STOCKS:
            code = item['code']
            name = item['name']
            sub_name = item['sub']
            sub_id = sub_map.get(sub_name)
            if sub_id is None:
                logger.warning(f'[seed.apple] 子分类 {sub_name} 查找失败，跳过 {code}')
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
                logger.debug(f'[seed.apple] {code} 已归属 category_id={sc.category_id}，保留不动')

        db.session.commit()

        if added_stock or added_category or parent_created:
            logger.info(
                f'[seed.apple] 完成 新增股票={added_stock} 新增归属={added_category} '
                f'保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.apple] 执行失败（忽略，不阻断启动）: {exc}')

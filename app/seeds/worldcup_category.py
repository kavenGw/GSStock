"""
FIFA 世界杯 2026（美加墨）主题板块 seed（幂等）

一级板块 "世界杯2026" + 二级板块（赛事硬件/赛事运营/赛事消费/赛事出行），
以及 21 只 A 股受益标的记录和归属。

幂等规则（遵循 CLAUDE.md 铁律）：
- 板块：同名同父存在 → 复用 id
- Stock：存在 → 跳过，不覆盖 stock_name
- StockCategory：已归属任何分类 → 保留原分类（保护跨板块引用）
- investment_advice：已有非空值 → 不覆盖
"""
import logging

logger = logging.getLogger(__name__)

WORLDCUP_PARENT = '世界杯2026'
SUBCATEGORIES = ['赛事硬件', '赛事运营', '赛事消费', '赛事出行']

WORLDCUP_STOCKS = [
    # 赛事硬件（上游）
    {'code': '605099', 'name': '共创草坪', 'sub': '赛事硬件',
     'advice': '人造草坪全球龙头，FIFA Preferred Producer 认证；产能以外销为主，美加墨赛事球场改造与更新周期受益。巴菲特视角定性：Keep Watching，护城河中等偏弱，贸易壁垒为核心风险。'},
    {'code': '300651', 'name': '金陵体育', 'sub': '赛事硬件',
     'advice': '篮球架/足球门/田径器材制造商，FIBA/FIFA/IAAF 认证。商业模式为政府与教育采购主导的 B2B 制造，定价权薄弱。巴菲特视角：Don\'t Buy（commodity business）。'},
    {'code': '605299', 'name': '舒华体育', 'sub': '赛事硬件',
     'advice': '健身器材制造商，政采路径+家用电商双主线。商品化陷阱明显，护城河轻微收窄。巴菲特视角：Don\'t Buy。'},
    {'code': '002899', 'name': '英派斯', 'sub': '赛事硬件', 'advice': ''},
    {'code': '603081', 'name': '大丰实业', 'sub': '赛事硬件', 'advice': ''},
    {'code': '601668', 'name': '中国建筑', 'sub': '赛事硬件', 'advice': ''},

    # 赛事运营（中游：运营+体彩+传媒）
    {'code': '600158', 'name': '中体产业', 'sub': '赛事运营',
     'advice': '国家体育总局背景综合控股平台，业务杂糅（场馆/健身/经纪/旅游），长期 ROE 低于成本、估值由题材驱动。巴菲特视角：Don\'t Buy（平庸生意+故事股）。'},
    {'code': '002229', 'name': '鸿博股份', 'sub': '赛事运营', 'advice': ''},
    {'code': '002605', 'name': '姚记科技', 'sub': '赛事运营', 'advice': ''},
    {'code': '002181', 'name': '粤传媒', 'sub': '赛事运营',
     'advice': '报业+户外广告，赛事营销承接。巴菲特视角：Don\'t Buy（传统媒体护城河持续衰退）。'},
    {'code': '600831', 'name': '广电网络', 'sub': '赛事运营', 'advice': ''},
    {'code': '002712', 'name': '思美传媒', 'sub': '赛事运营', 'advice': ''},

    # 赛事消费（下游：鞋服+食品饮料）
    {'code': '603555', 'name': '贵人鸟', 'sub': '赛事消费', 'advice': ''},
    {'code': '300005', 'name': '探路者', 'sub': '赛事消费', 'advice': ''},
    {'code': '002832', 'name': '比音勒芬', 'sub': '赛事消费', 'advice': ''},
    {'code': '603908', 'name': '牧高笛', 'sub': '赛事消费', 'advice': ''},
    {'code': '600600', 'name': '青岛啤酒', 'sub': '赛事消费', 'advice': ''},
    {'code': '000729', 'name': '燕京啤酒', 'sub': '赛事消费', 'advice': ''},
    {'code': '600887', 'name': '伊利股份', 'sub': '赛事消费', 'advice': ''},

    # 赛事出行
    {'code': '601111', 'name': '中国国航', 'sub': '赛事出行', 'advice': ''},
    {'code': '002707', 'name': '众信旅游', 'sub': '赛事出行', 'advice': ''},
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


def seed_worldcup_category():
    """幂等 seed：世界杯 2026 主题板块 + 股票 + 归属 + 可选投资建议。

    失败不抛出（启动不可被阻断），遵循 CLAUDE.md 铁律：
    已存在的 stock_name / investment_advice / StockCategory 归属一律不覆盖。
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import StockCategory

    try:
        parent, parent_created = _get_or_create_category(WORLDCUP_PARENT, parent_id=None)
        if parent_created:
            logger.info(f'[seed.worldcup] 创建一级板块 {WORLDCUP_PARENT} id={parent.id}')

        sub_map = {}
        for sub_name in SUBCATEGORIES:
            sub, created = _get_or_create_category(sub_name, parent_id=parent.id)
            sub_map[sub_name] = sub.id
            if created:
                logger.info(f'[seed.worldcup] 创建二级板块 {sub_name} id={sub.id}')

        added_stock = 0
        added_category = 0
        added_advice = 0
        skipped_category = 0

        for item in WORLDCUP_STOCKS:
            code = item['code']
            name = item['name']
            sub_name = item['sub']
            advice = item.get('advice', '')
            sub_id = sub_map.get(sub_name)
            if sub_id is None:
                logger.warning(f'[seed.worldcup] 子分类 {sub_name} 查找失败，跳过 {code}')
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
                logger.debug(f'[seed.worldcup] {code} 已归属 category_id={sc.category_id}，保留不动')

            if advice and not (stock.investment_advice or '').strip():
                stock.investment_advice = advice
                added_advice += 1

        db.session.commit()

        if added_stock or added_category or added_advice or parent_created:
            logger.info(
                f'[seed.worldcup] 完成 新增股票={added_stock} 新增归属={added_category} '
                f'写入建议={added_advice} 保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.worldcup] 执行失败（忽略，不阻断启动）: {exc}')

"""CCL 上游电子布板块 seed（幂等）

将电子级玻璃纤维布等 CCL 上游材料标的注入"PCB材料"分类（与生益科技同级）。
同分类已存在的标的（如 600183 生益科技）受铁律保护，仅在新增标的时生效。

幂等规则（遵循 CLAUDE.md 铁律）：
- Stock：存在 → 跳过，不覆盖 stock_name / investment_advice
- StockCategory：已归属任何分类 → 保留原分类
"""
import logging

logger = logging.getLogger(__name__)

CCL_UPSTREAM_PARENT = 'PCB材料'

CCL_UPSTREAM_STOCKS = [
    {
        'code': '603256',
        'name': '宏和科技',
        'advice': (
            '电子级玻璃纤维布厂商，CCL 上游核心材料（玻纤布→CCL→PCB→AI 服务器）。'
            '26Q1 单季净利 1.4 亿（+354%）/毛利率 55.65%（历史新高），反映 AI 高端 Low Df '
            '电子布红利启动；但 2023 年曾净利转亏（毛利率被压至 8.83%）暴露其商品型周期本质。'
            '当前 PE 418x / PB 47x（5y 99.8% 分位，史上最贵），1304 亿市值已极致定价 AI 故事。'
            '同属 CCL 产业链（生益/南亚新材的更上游）。买点：PE < 20x 或市值 < 160 亿（约 18 元）。'
        ),
    },
]


def _lookup_or_create_category(name):
    """优先复用已存在的同名分类（不限 parent_id），缺失才创建顶级分类。

    避免与既有的二级分类（如 parent_id=3 下的 'PCB材料'）产生重名重复。
    """
    from app.models.category import Category
    from app import db

    existing = Category.query.filter_by(name=name).first()
    if existing:
        return existing, False

    category = Category(name=name, parent_id=None)
    db.session.add(category)
    db.session.commit()
    return category, True


def seed_ccl_upstream_category():
    """幂等 seed：CCL 上游电子布标的注入 PCB材料 分类。

    失败不抛出（启动不可被阻断）。已存在的 stock_name / investment_advice / StockCategory
    归属一律不覆盖。
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import StockCategory

    try:
        parent, parent_created = _lookup_or_create_category(CCL_UPSTREAM_PARENT)
        if parent_created:
            logger.info(f'[seed.ccl_upstream] 创建分类 {CCL_UPSTREAM_PARENT} id={parent.id}')

        added_stock = 0
        added_advice = 0
        added_category = 0
        skipped_category = 0

        for item in CCL_UPSTREAM_STOCKS:
            code = item['code']
            name = item['name']
            advice = item['advice']

            stock = Stock.query.get(code)
            if not stock:
                stock = Stock(stock_code=code, stock_name=name, investment_advice=advice)
                db.session.add(stock)
                db.session.flush()
                added_stock += 1
                added_advice += 1
            elif not stock.investment_advice:
                stock.investment_advice = advice
                added_advice += 1

            sc = StockCategory.query.filter_by(stock_code=code).first()
            if not sc:
                db.session.add(StockCategory(stock_code=code, category_id=parent.id))
                added_category += 1
            elif sc.category_id != parent.id:
                skipped_category += 1
                logger.debug(f'[seed.ccl_upstream] {code} 已归属 category_id={sc.category_id}，保留不动')

        db.session.commit()

        if added_stock or added_category or added_advice:
            logger.info(
                f'[seed.ccl_upstream] 完成 新增股票={added_stock} 新增 advice={added_advice} '
                f'新增归属={added_category} 保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.ccl_upstream] 执行失败（忽略，不阻断启动）: {exc}')

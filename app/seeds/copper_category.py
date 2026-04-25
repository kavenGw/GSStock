"""
铜产业链板块 seed（幂等）

一级板块 "铜产业链" + 二级板块（铜矿资源/铜冶炼/铜加工/铜下游应用），
覆盖紫金/洛阳钼/江西铜/铜陵/海亮等核心标的。

幂等规则（遵循 CLAUDE.md 铁律）：
- 板块：同名同父存在 → 复用 id
- Stock：存在 → 跳过，不覆盖 stock_name
- StockCategory：已归属任何分类 → 保留原分类（保护跨板块引用）
- investment_advice：已有非空值 → 不覆盖
"""
import logging

logger = logging.getLogger(__name__)

COPPER_PARENT = '铜产业链'
SUBCATEGORIES = ['铜矿资源', '铜冶炼', '铜加工', '铜下游应用']

COPPER_STOCKS = [
    # 铜矿资源（上游）
    {'code': '601899', 'name': '紫金矿业', 'sub': '铜矿资源',
     'advice': '全球前十铜矿商 + 国内最大金铜矿龙头。当前估值偏高（PB/PE 均在历史高分位）。'
               '巴菲特视角：Don\'t Buy（高估应减持，等周期回落）。'},
    {'code': '603993', 'name': '洛阳钼业', 'sub': '铜矿资源',
     'advice': '刚果金 TFM/KFM 铜钴双矿主力，资源禀赋顶级但估值贵。'
               '巴菲特视角：Don\'t Buy（仅在铜价回落至 6500 USD/t 以下 + PB<1.5 + 正自由现金流三重条件才考虑深度研究）。'},
    {'code': '601168', 'name': '西部矿业', 'sub': '铜矿资源', 'advice': ''},
    {'code': '600489', 'name': '中金黄金', 'sub': '铜矿资源',
     'advice': '黄金为主、铜为副，金铜伴生。当前金价高位 + 公司护城河弱。'
               '巴菲特视角：Don\'t Buy（持仓者建议逐步减持兑现金价周期红利）。'},

    # 铜冶炼（上游）
    {'code': '600362', 'name': '江西铜业', 'sub': '铜冶炼', 'advice': ''},
    {'code': '000630', 'name': '铜陵有色', 'sub': '铜冶炼', 'advice': ''},
    {'code': '000878', 'name': '云南铜业', 'sub': '铜冶炼', 'advice': ''},

    # 铜加工（中游：铜管/铜带/铜箔）
    {'code': '002203', 'name': '海亮股份', 'sub': '铜加工', 'advice': ''},
    {'code': '002295', 'name': '精艺股份', 'sub': '铜加工', 'advice': ''},
    {'code': '002171', 'name': '楚江新材', 'sub': '铜加工', 'advice': ''},
    {'code': '601137', 'name': '博威合金', 'sub': '铜加工', 'advice': ''},
    {'code': '601609', 'name': '金田股份', 'sub': '铜加工', 'advice': ''},
    {'code': '600255', 'name': '鑫科材料', 'sub': '铜加工', 'advice': ''},
    {'code': '600110', 'name': '诺德股份', 'sub': '铜加工', 'advice': ''},

    # 铜下游应用（下游：电网/新能源/AI 数据中心）
    # 注：300750/600406/002028/002850/002130/688668/300252 已归属其它分类（energy_storage/nvidia 链），
    # 受 StockCategory 唯一约束保护，本 seed 不会改动其归属，仅在 Stock 表幂等补名。
    {'code': '300750', 'name': '宁德时代', 'sub': '铜下游应用', 'advice': ''},
    {'code': '600406', 'name': '国电南瑞', 'sub': '铜下游应用', 'advice': ''},
    {'code': '002028', 'name': '思源电气', 'sub': '铜下游应用', 'advice': ''},
    {'code': '002850', 'name': '科达利', 'sub': '铜下游应用', 'advice': ''},
    {'code': '002130', 'name': '沃尔核材', 'sub': '铜下游应用', 'advice': ''},
    {'code': '688668', 'name': '鼎通科技', 'sub': '铜下游应用', 'advice': ''},
    {'code': '300252', 'name': '金信诺', 'sub': '铜下游应用', 'advice': ''},
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


def seed_copper_category():
    """幂等 seed：铜产业链板块 + 股票 + 归属 + 可选投资建议。

    失败不抛出（启动不可被阻断），遵循 CLAUDE.md 铁律：
    已存在的 stock_name / investment_advice / StockCategory 归属一律不覆盖。
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import StockCategory

    try:
        parent, parent_created = _get_or_create_category(COPPER_PARENT, parent_id=None)
        if parent_created:
            logger.info(f'[seed.copper] 创建一级板块 {COPPER_PARENT} id={parent.id}')

        sub_map = {}
        for sub_name in SUBCATEGORIES:
            sub, created = _get_or_create_category(sub_name, parent_id=parent.id)
            sub_map[sub_name] = sub.id
            if created:
                logger.info(f'[seed.copper] 创建二级板块 {sub_name} id={sub.id}')

        added_stock = 0
        added_category = 0
        added_advice = 0
        skipped_category = 0

        for item in COPPER_STOCKS:
            code = item['code']
            name = item['name']
            sub_name = item['sub']
            advice = item.get('advice', '')
            sub_id = sub_map.get(sub_name)
            if sub_id is None:
                logger.warning(f'[seed.copper] 子分类 {sub_name} 查找失败，跳过 {code}')
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
                logger.debug(f'[seed.copper] {code} 已归属 category_id={sc.category_id}，保留不动')

            if advice and not (stock.investment_advice or '').strip():
                stock.investment_advice = advice
                added_advice += 1

        db.session.commit()

        if added_stock or added_category or added_advice or parent_created:
            logger.info(
                f'[seed.copper] 完成 新增股票={added_stock} 新增归属={added_category} '
                f'写入建议={added_advice} 保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.copper] 执行失败（忽略，不阻断启动）: {exc}')

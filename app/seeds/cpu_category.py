"""
CPU 产业链板块 seed（幂等）

启动时确保数据库存在：
- 一级板块 "CPU"
- 二级子板块：国产CPU设计 / Intel供应链 / AMD供应链 / CPU封测
- 相关 A 股股票记录与分类归属
- 每只股票的投资建议

幂等规则：
- 板块：同名同父存在 → 复用 id，不重复创建
- Stock：存在 → 跳过，不覆盖 stock_name
- StockCategory：**已归属任何分类 → 保留原分类**（保护现有 PCB/存储等分类）
- investment_advice：已有非空值 → 不覆盖
"""
import logging

logger = logging.getLogger(__name__)

CPU_PARENT = 'CPU'
SUBCATEGORIES = ['国产CPU设计', 'Intel供应链', 'AMD供应链', 'CPU封测']

CPU_STOCKS = [
    {
        'code': '688047',
        'name': '龙芯中科',
        'sub': '国产CPU设计',
        'advice': (
            '产业链地位：A股唯一完全自主 LoongArch 指令集 CPU 设计商，'
            '3A6000/3C5000/2K2000 系列覆盖桌面/服务器/工控，党政军信创核心供应商。'
            '关键业绩：CPU 及配套芯片为绝对主营（>95% 营收），近年营收与信创招标节奏强相关，'
            '利润受研发投入与商业化落地节奏影响，波动较大。'
            '风险提示：信创招标周期性明显，生态薄弱制约商业化；晶圆代工受国际制裁风险。'
            '操作建议：长期布局标的，跟踪党政军招标公告与生态伙伴进展；短期波动大，分批建仓、回调加仓为宜。'
        ),
    },
    {
        'code': '688041',
        'name': '海光信息',
        'sub': '国产CPU设计',
        'advice': (
            '产业链地位：Hygon C86 架构（AMD Zen 授权）国产服务器 CPU 龙头，'
            'CPU+DCU 协处理器双主线，运营商/金融/政企信创主力供应商，大陆生态最成熟的 x86 兼容路线。'
            '关键业绩：营收以服务器 CPU 为主，DCU（AI 加速）成长贡献提升，毛利率居国产 CPU 前列。'
            '风险提示：AMD 授权延续性与美国出口管制政策为核心风险；DCU 生态与 CUDA 存在代际差。'
            '操作建议：AI+信创双主线核心标的，估值偏高但业绩成长性强；关注美国实体清单变动与 DCU 出货放量信号。'
        ),
    },
    {
        'code': '002916',
        'name': '深南电路',
        'sub': 'Intel供应链',
        'advice': (
            '产业链地位：A股 FC-BGA/ABF 封装基板龙头，广州/无锡基板厂公开披露进入 Intel 合格供应商名单，'
            '是国产 CPU 封装基板替代首选；同时为 PCB 与光电子两大主业提供协同。'
            '关键业绩：PCB 业务稳健，封装基板受益国产替代与 AI 服务器扩容，毛利率与产能利用率处上行通道。'
            '风险提示：基板扩产周期长、资本开支大；下游服务器景气与 Intel 平台迭代节奏直接影响订单。'
            '操作建议：长期看好封装基板国产替代，关注基板产能爬坡节奏与大客户认证进度；回调是布局窗口。'
        ),
    },
    {
        'code': '002436',
        'name': '兴森科技',
        'sub': 'Intel供应链',
        'advice': (
            '产业链地位：广州兴森半导体 FC-BGA 基板项目向北美 CPU 大客户（Intel）小批量供货并扩产，'
            '同时为 PCB 样板快件龙头，双主业布局。'
            '关键业绩：PCB 样板业务稳定现金流，FC-BGA 处于量产爬坡期，2024 年以来新订单持续放量。'
            '风险提示：基板量产良率尚未稳定，大客户认证仍在推进；新建产能折旧压力阶段性拖累毛利。'
            '操作建议：赛道估值弹性品种，关注 FC-BGA 良率/产能爬坡季报披露；宜分批建仓，止损参考前低。'
        ),
    },
    {
        'code': '601138',
        'name': '工业富联',
        'sub': 'Intel供应链',
        'advice': (
            '产业链地位：全球最大 Intel 平台服务器 ODM，云计算业务深度绑定 Intel Xeon 迭代节奏；'
            '同时是英伟达 GB200/HGX AI 服务器核心代工商，AI 算力链与传统 x86 服务器链双轮驱动。'
            '关键业绩：云计算分部营收高增，AI 服务器订单持续突破，毛利率结构优化；Intel/AMD CPU 平台迭代直接影响出货。'
            '风险提示：ODM 毛利较薄；地缘政治与关税波动；超大客户集中度高。'
            '操作建议：AI 算力链核心权重标的，估值相对合理；关注英伟达 GB200 出货节奏与 Intel/AMD 服务器新平台推出。'
        ),
    },
    {
        'code': '002156',
        'name': '通富微电',
        'sub': 'AMD供应链',
        'advice': (
            '产业链地位：与 AMD 合资通富超威（TFAMD，苏州+槟城两厂），承接 AMD 绝大部分 CPU/APU/GPU 封测，'
            'AMD 为第一大客户且营收占比长期 60%+；是国内唯一大规模量产服务器 CPU 先进封装的厂商。'
            '关键业绩：营收与 AMD Zen4/Zen5 CPU 及 MI 系列 GPU 出货强相关，近年受益 AI 服务器与 EPYC 扩张。'
            '风险提示：单客户依赖度高，AMD 业绩波动传导明显；先进封装资本开支压力大。'
            '操作建议：AMD 业绩代理标的，跟踪 AMD 季报与 MI 系列出货指引；宜在 AMD 指引平淡时逢低布局。'
        ),
    },
    {
        'code': '600584',
        'name': '长电科技',
        'sub': 'CPU封测',
        'advice': (
            '产业链地位：全球封测前三、大陆龙头，旗下长电先进（JCAP）+ 星科金朋（JSCK）具备 2.5D/FCBGA/Chiplet '
            '高端封装能力，客户覆盖高通、海思、博通、Marvell 等，独立第三方多客户型。'
            '关键业绩：高端先进封装占比持续提升，受益 AI SoC 与服务器 CPU 国产化需求，毛利率分化向好。'
            '风险提示：消费电子周期对中低端封测拖累仍存；海外大客户订单波动。'
            '操作建议：封测赛道核心标的，估值中枢稳健；关注先进封装产能利用率与海外客户订单回暖节奏。'
        ),
    },
    {
        'code': '002185',
        'name': '华天科技',
        'sub': 'CPU封测',
        'advice': (
            '产业链地位：大陆封测第三大厂商，昆山厂 Bumping/FC/2.5D 线布局高端封装，'
            '承接海思、兆芯、澜起等国产 CPU/SoC 订单，独立第三方多客户型。'
            '关键业绩：高端占比弱于长电但追赶明显，近年受益存储与国产 CPU 订单放量，毛利率修复。'
            '风险提示：先进封装产能爬坡期折旧压力大；与海外龙头在超高端工艺存在代差。'
            '操作建议：国产替代弹性品种，关注昆山先进封装项目投产进度与重点客户出货；适合中线跟踪。'
        ),
    },
]


def _get_or_create_category(name, parent_id=None):
    """返回 (category, created)，已存在则复用"""
    from app.models.category import Category
    from app import db

    existing = Category.query.filter_by(name=name, parent_id=parent_id).first()
    if existing:
        return existing, False

    category = Category(name=name, parent_id=parent_id)
    db.session.add(category)
    db.session.commit()
    return category, True


def seed_cpu_category():
    """幂等 seed：CPU 产业链一级+二级板块、股票、归属、投资建议。

    设计原则：
    - 已存在的分类/股票/归属**一律不覆盖**
    - 只补齐缺失项
    - 失败不抛出，只记录日志（启动不可被 seed 阻断）
    """
    from app import db
    from app.models.stock import Stock
    from app.models.category import Category, StockCategory

    try:
        parent, parent_created = _get_or_create_category(CPU_PARENT, parent_id=None)
        if parent_created:
            logger.info(f'[seed.cpu] 创建一级板块 {CPU_PARENT} id={parent.id}')

        sub_map = {}
        for sub_name in SUBCATEGORIES:
            sub, created = _get_or_create_category(sub_name, parent_id=parent.id)
            sub_map[sub_name] = sub.id
            if created:
                logger.info(f'[seed.cpu] 创建二级板块 {sub_name} id={sub.id}')

        added_stock = 0
        added_category = 0
        added_advice = 0
        skipped_category = 0

        for item in CPU_STOCKS:
            code = item['code']
            name = item['name']
            sub_name = item['sub']
            advice = item['advice']
            sub_id = sub_map.get(sub_name)
            if sub_id is None:
                logger.warning(f'[seed.cpu] 子分类 {sub_name} 查找失败，跳过 {code}')
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
                logger.debug(f'[seed.cpu] {code} 已归属 category_id={sc.category_id}，保留不动')

            if not (stock.investment_advice or '').strip():
                stock.investment_advice = advice
                added_advice += 1

        db.session.commit()

        if added_stock or added_category or added_advice or parent_created:
            logger.info(
                f'[seed.cpu] 完成 新增股票={added_stock} 新增归属={added_category} '
                f'写入建议={added_advice} 保留已有归属={skipped_category}'
            )
    except Exception as exc:
        db.session.rollback()
        logger.warning(f'[seed.cpu] 执行失败（忽略，不阻断启动）: {exc}')

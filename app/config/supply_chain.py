# 供应链知识图谱配置
# 以核心公司为中心，映射上下游产业链关系

SUPPLY_CHAIN_GRAPHS = {
    'lumentum': {
        'name': 'Lumentum',
        'code': 'LITE',
        'description': '全球光芯片/光模块/激光器/激光雷达源头',
        'core': {
            'technologies': ['EML', 'VCSEL', 'MEMS', 'OCS', 'CPO'],
            'products': ['光传输模块', '硅光芯片', '3D传感', '激光雷达'],
            'customers': ['苹果', '思科', '华为', 'Meta', '微软'],
        },
        'upstream': {
            '衬底材料': {
                'description': '光芯片核心衬底和外延材料',
                'companies': {
                    '300316': {'name': '晶盛机电', 'role': '碳化硅晶棒、蓝宝石衬底'},
                    '600330': {'name': '天通股份', 'role': '蓝宝石衬底/压电晶体材料'},
                    '600703': {'name': '三安光电', 'role': '光芯片/磷化铟(InP)基础芯片', 'tag': 'frontEC'},
                },
            },
            '芯片光刻设备': {
                'description': '光芯片制造核心设备',
                'companies': {
                    '002371': {'name': '北方华创', 'role': '薄膜沉积/刻蚀设备'},
                    '688012': {'name': '中微公司', 'role': '刻蚀设备'},
                },
            },
            '光学元件': {
                'description': '光学核心元器件',
                'companies': {
                    '688195': {'name': '腾景科技', 'role': '滤光片、棱镜、隔离器(WSOCS)'},
                    '002222': {'name': '福晶科技', 'role': '非线性光学晶体(OCS晶体)'},
                    '603297': {'name': '永新光学', 'role': '光学镜片、TPLN消耗制品(>70%)'},
                },
            },
        },
        'midstream': {
            'CPO光引擎/封装': {
                'description': 'CPO共封装光学模块',
                'companies': {
                    '300394': {'name': '天孚通信', 'role': 'CPO光引擎、连接器、CPO/OCS封装'},
                    '300308': {'name': '中际旭创', 'role': '800G光模块、CPO/OCS封装'},
                },
            },
            '光模块': {
                'description': '高速光通信模块',
                'companies': {
                    '300502': {'name': '新易盛', 'role': '400G/800G光模块'},
                    '000988': {'name': '华工科技', 'role': '光模块'},
                },
            },
            '光芯片/光纤': {
                'description': '核心光芯片与光纤器件',
                'companies': {
                    '002281': {'name': '光迅科技', 'role': '光芯片EML/DFB → 800G/1.6T'},
                    '601869': {'name': '长飞光纤', 'role': '光纤光缆、LCoS封装'},
                    '300620': {'name': '光库科技', 'role': '铌酸锂调制器'},
                },
            },
        },
        'downstream': {
            '电信网络': {'description': '5G/6G光通信网络'},
            '消费电子': {'description': '3D传感/AR/VR'},
            'AI数据中心': {'description': '云计算(AWS/Meta)、AI训练推理'},
        },
        'competitors': {
            'COHR': {'name': 'Coherent (II-VI)', 'market': 'US'},
            'AVGO': {'name': 'Broadcom(博通)', 'market': 'US'},
            '002281': {'name': '光迅科技', 'market': 'A'},
            '300620': {'name': '光库科技', 'market': 'A'},
        },
        'trends': {
            'bandwidth': '800G → 1.6T → 3.2T',
            'technologies': ['CPO共封装光学', '硅光集成', '激光雷达'],
            'china_role': '材料/光元件/代工封装基础完备',
        },
    },
    'cpu': {
        'name': 'Intel',
        'code': 'INTC',
        'description': 'x86 CPU 双寡头 + 国产替代产业链',
        'core': {
            'technologies': ['x86', 'Zen', 'Core/Xeon', 'Chiplet', '先进封装'],
            'products': ['桌面CPU', '服务器CPU', 'AI加速卡(DCU/GPU)', 'APU'],
            'customers': ['数据中心', 'PC OEM', '信创政企', '云服务商'],
        },
        'extra_cores': [
            {
                'code': 'AMD',
                'name': 'AMD',
                'market': 'US',
                'description': 'x86 CPU/GPU 双线龙头，Zen 架构授权海光',
            },
        ],
        'upstream': {
            '封装基板': {
                'description': 'FC-BGA / ABF 封装基板（CPU 关键载体）',
                'companies': {
                    '002916': {'name': '深南电路', 'role': 'FC-BGA 基板，Intel 合格供应商'},
                    '002436': {'name': '兴森科技', 'role': 'FC-BGA 小批量供货北美 CPU 大客户'},
                },
            },
        },
        'midstream': {
            '服务器 ODM': {
                'description': '基于 Intel/AMD 平台的服务器代工',
                'companies': {
                    '601138': {'name': '工业富联', 'role': '全球最大 Intel 服务器 ODM，AI 服务器核心代工'},
                },
            },
            'CPU 封测': {
                'description': 'CPU / APU / GPU 先进封装测试',
                'companies': {
                    '002156': {'name': '通富微电', 'role': 'AMD 合资 TFAMD，承接 AMD 绝大部分 CPU/APU/GPU 封测'},
                    '600584': {'name': '长电科技', 'role': '全球前三封测，FCBGA/Chiplet 高端封装'},
                    '002185': {'name': '华天科技', 'role': '国内第三大封测，承接国产 CPU/SoC'},
                },
            },
        },
        'downstream': {
            'AI 数据中心': {'description': '超大规模云与 AI 训练推理'},
            'PC / 桌面': {'description': '消费级 CPU'},
            '信创政企': {'description': '党政军国产化替代'},
        },
        'competitors': {
            '688041': {'name': '海光信息', 'market': 'A'},
            '688047': {'name': '龙芯中科', 'market': 'A'},
        },
        'trends': {
            'bandwidth': '5nm → 3nm → 2nm 制程',
            'technologies': ['Chiplet', '先进封装', 'AI 算力集成', '国产替代'],
            'china_role': '封装基板+封测+ODM 全栈配套，海光/龙芯双路线突破',
        },
    },
    'worldcup_2026': {
        'name': 'FIFA 世界杯 2026',
        'code': 'WC2026',
        'description': '美加墨 48 队扩军世界杯（2026.6.11–7.19），A 股受益链条主题映射',
        'core': {
            'technologies': ['FIFA 官方认证', '全球转播权', '场馆基建', '赞助体系'],
            'products': ['48队104场赛事', '3国16城场馆', '全球百亿观众', '官方周边商品'],
            'customers': ['品牌赞助商', '转播商', '球迷消费', '体彩/博彩'],
        },
        'upstream': {
            '人造草坪': {
                'description': '球场草坪供应（FIFA Preferred Producer）',
                'companies': {
                    '605099': {'name': '共创草坪', 'role': '全球人造草坪龙头、FIFA 认证', 'tag': 'keep_watching'},
                },
            },
            '体育器材': {
                'description': '赛事器材、训练与健身设备',
                'companies': {
                    '300651': {'name': '金陵体育', 'role': '篮球架/足球门/田径器材 FIBA/FIFA 认证', 'tag': 'don_buy'},
                    '605299': {'name': '舒华体育', 'role': '商用/家用健身器材', 'tag': 'don_buy'},
                    '002899': {'name': '英派斯', 'role': '商用健身器材、场馆配套', 'tag': 'not_analyzed'},
                },
            },
            '场馆建设': {
                'description': '文体场馆建设与看台/舞美设施',
                'companies': {
                    '603081': {'name': '大丰实业', 'role': '文体场馆看台、舞美灯光', 'tag': 'not_analyzed'},
                    '601668': {'name': '中国建筑', 'role': '海外基建，美加墨场馆改造概念', 'tag': 'not_analyzed'},
                },
            },
        },
        'midstream': {
            '赛事运营': {
                'description': '赛事承办、经纪与综合体育平台',
                'companies': {
                    '600158': {'name': '中体产业', 'role': '国家体育总局背景综合平台', 'tag': 'don_buy'},
                },
            },
            '体彩/彩票': {
                'description': '彩票印刷、销售系统与主题题材',
                'companies': {
                    '002229': {'name': '鸿博股份', 'role': '彩票印刷龙头、世界杯体彩脉冲', 'tag': 'not_analyzed'},
                    '002605': {'name': '姚记科技', 'role': '扑克+互联网彩票、赛事主题活跃', 'tag': 'not_analyzed'},
                },
            },
            '传媒转播': {
                'description': '赛事转播、报业营销与整合广告',
                'companies': {
                    '002181': {'name': '粤传媒', 'role': '报业+户外广告、赛事营销承接', 'tag': 'don_buy'},
                    '600831': {'name': '广电网络', 'role': '陕西有线、赛事直播渠道', 'tag': 'not_analyzed'},
                    '002712': {'name': '思美传媒', 'role': '整合营销、赛事赞助代理', 'tag': 'not_analyzed'},
                },
            },
        },
        'downstream': {
            '运动鞋服': {
                'description': '大众运动品牌与户外鞋服，赛事主题消费承接',
                'companies': {
                    '603555': {'name': '贵人鸟', 'role': '大众运动鞋服品牌', 'tag': 'not_analyzed'},
                    '300005': {'name': '探路者', 'role': '户外运动品牌', 'tag': 'not_analyzed'},
                    '002832': {'name': '比音勒芬', 'role': '高尔夫运动服饰', 'tag': 'not_analyzed'},
                    '603908': {'name': '牧高笛', 'role': '露营帐篷、观赛衍生场景', 'tag': 'not_analyzed'},
                },
            },
            '食品饮料': {
                'description': '啤酒/乳制品主题消费脉冲（历届世界杯规律）',
                'companies': {
                    '600600': {'name': '青岛啤酒', 'role': '世界杯主题消费脉冲', 'tag': 'not_analyzed'},
                    '000729': {'name': '燕京啤酒', 'role': '北方啤酒龙头、赛事营销', 'tag': 'not_analyzed'},
                    '600887': {'name': '伊利股份', 'role': '历届世界杯赞助商/主题营销', 'tag': 'not_analyzed'},
                },
            },
            '出行旅游': {
                'description': '观赛出境游、北美航线受益',
                'companies': {
                    '601111': {'name': '中国国航', 'role': '北美航线、赛事出行', 'tag': 'not_analyzed'},
                    '002707': {'name': '众信旅游', 'role': '出境游、世界杯观赛团', 'tag': 'not_analyzed'},
                },
            },
        },
        'competitors': {},
        'trends': {
            'bandwidth': '2026.6.11 开赛 → 2026.7.19 决赛',
            'technologies': ['主题消费脉冲', '体彩销售激增', '赛事转播权分销'],
            'china_role': '制造端（草坪/器材）主力，消费端（赞助/出行）承接',
        },
    },
    'ascend': {
        'name': '华为昇腾',
        'code': 'HUAWEI',
        'description': '昇腾 Atlas 950/960 SuperPoD 超节点 + 国产 AI 算力全栈',
        'core': {
            'technologies': ['昇腾910C', 'Atlas 950/960', 'SuperPoD 超节点',
                             'CloudMatrix 384', 'CANN', 'MindSpore'],
            'products': ['AI训练集群', 'AI推理服务器', '昇腾加速模块', '大模型一体机'],
            'customers': ['三大运营商', '政企信创', '央国企', '头部互联网', '大模型厂商'],
        },
        'upstream': {
            'PCB/封装基板': {
                'description': 'AI 服务器高多层 PCB / HDI / 基板',
                'companies': {
                    '002463': {'name': '沪电股份', 'role': 'AI 服务器高多层 PCB 龙头'},
                    '600183': {'name': '生益科技', 'role': '高频高速覆铜板'},
                    '002916': {'name': '深南电路', 'role': 'FC-BGA 基板 / 通信 PCB（同属 CPU 产业链）'},
                },
            },
            '光互连元件': {
                'description': '超节点内部 Scale-up 光互连核心元件',
                'companies': {
                    '300316': {'name': '晶盛机电', 'role': '碳化硅/蓝宝石衬底'},
                    '688195': {'name': '腾景科技', 'role': '滤光片/隔离器'},
                    '002222': {'name': '福晶科技', 'role': '非线性光学晶体'},
                },
            },
            '液冷散热': {
                'description': 'AI 服务器液冷核心供应商',
                'companies': {
                    '002837': {'name': '英维克', 'role': '数据中心液冷龙头'},
                    '300499': {'name': '高澜股份', 'role': '液冷温控'},
                    '300602': {'name': '飞荣达', 'role': '导热散热材料'},
                },
            },
        },
        'midstream': {
            '昇腾整机 ODM': {
                'description': '昇腾 Atlas 服务器整机代工与品牌',
                'companies': {
                    '603019': {'name': '中科曙光', 'role': '昇腾服务器深度合作，国产算力龙头'},
                    '000628': {'name': '高新发展', 'role': '华鲲振宇控股股东，昇腾整机主力'},
                    '600839': {'name': '四川长虹', 'role': '天宫实验室合资，昇腾服务器'},
                    '601138': {'name': '工业富联', 'role': 'AI 服务器 ODM 全球龙头（同属 CPU 产业链）'},
                },
            },
            '光模块': {
                'description': '超节点 Scale-up / Scale-out 光模块',
                'companies': {
                    '300308': {'name': '中际旭创', 'role': '800G/1.6T 光模块龙头'},
                    '300502': {'name': '新易盛', 'role': '800G 光模块'},
                    '300394': {'name': '天孚通信', 'role': 'CPO 光引擎/连接器'},
                    '000988': {'name': '华工科技', 'role': '光模块/激光'},
                    '002281': {'name': '光迅科技', 'role': '光芯片 EML/DFB'},
                },
            },
            '软件生态与分销': {
                'description': '昇腾 CANN/MindSpore 适配、行业解决方案、分销渠道',
                'companies': {
                    '002261': {'name': '拓维信息', 'role': '昇腾鲲鹏整机 + 鸿蒙教育，生态核心'},
                    '000158': {'name': '常山北明', 'role': '鲲鹏昇腾适配 + 政务信创'},
                    '000034': {'name': '神州数码', 'role': '华为昇腾 A 级总经销商'},
                    '301236': {'name': '软通动力', 'role': '华为生态服务龙头 + 鸿蒙欧拉'},
                    '600498': {'name': '烽火通信', 'role': '光传输 + 昇腾合作'},
                },
            },
        },
        'downstream': {
            '政企信创': {'description': '党政军 / 央国企国产算力替代'},
            'AI 数据中心': {'description': '三大运营商智算中心、头部云厂商昇腾集群'},
            '大模型训练': {'description': '国产千亿/万亿参数大模型训练与推理'},
            '自动驾驶/车载': {'description': '昇腾车载 AI 方案（Mate/问界生态）'},
        },
        'competitors': {
            '688256': {'name': '寒武纪', 'market': 'A'},
            '688041': {'name': '海光信息', 'market': 'A'},
            '300474': {'name': '景嘉微', 'market': 'A'},
            'NVDA':   {'name': 'NVIDIA', 'market': 'US'},
        },
        'trends': {
            'bandwidth': '昇腾910B → 910C → Atlas 950 SuperPoD(384卡)',
            'technologies': ['超节点 Scale-up', 'CloudMatrix', '全光互连', '液冷',
                             '自主生态 CANN/MindSpore'],
            'china_role': '芯片自主 + 整机 ODM + 光互连 + 液冷全栈国产化',
        },
    },
    'beer': {
        'name': '青岛啤酒',
        'code': '600600',
        'description': '中国啤酒 CR5 + 高端化主线 + 全球化品牌代表',
        'core': {
            'technologies': ['纯生酿造', '全麦芽工艺', '高端化双品牌', '物流半径成本结构'],
            'products': ['青岛经典', '青岛纯生', '奥古特', '一厂 1903', '白啤/皮尔森'],
            'customers': ['餐饮渠道', '商超/便利店', '电商/即时零售', '夜场/精酿吧', '出口海外'],
        },
        'extra_cores': [
            {
                'code': '0291.HK',
                'name': '华润啤酒',
                'market': 'HK',
                'description': '雪花品牌 + 收购喜力中国，A股啤酒销量第一（Not Analyzed）',
            },
            {
                'code': '600132',
                'name': '重庆啤酒',
                'market': 'A',
                'description': '嘉士伯 60% 控股，乌苏+1664+乐堡高端矩阵（Keep Watching）',
            },
            {
                'code': '000729',
                'name': '燕京啤酒',
                'market': 'A',
                'description': 'U8 大单品复兴 + 北方市场基本盘（Not Analyzed）',
            },
        ],
        'upstream': {
            '金属包装': {
                'description': '啤酒易拉罐/金属罐头部供应商',
                'companies': {
                    '002701': {'name': '奥瑞金', 'role': '易拉罐龙头，百威/青啤/华润核心供应', 'tag': 'not_analyzed'},
                    '601968': {'name': '宝钢包装', 'role': '金属罐/二片罐，全国产能布局', 'tag': 'not_analyzed'},
                },
            },
            '玻璃包装': {
                'description': '啤酒玻璃瓶 / 浮法玻璃',
                'companies': {
                    '600876': {'name': '洛阳玻璃', 'role': '浮法玻璃/日用玻璃', 'tag': 'not_analyzed'},
                    '000012': {'name': '南玻A', 'role': '玻璃综合龙头', 'tag': 'not_analyzed'},
                },
            },
            '纸箱瓦楞包装': {
                'description': '啤酒外箱与瓦楞纸包装',
                'companies': {
                    '002228': {'name': '合兴包装', 'role': '瓦楞纸箱龙头', 'tag': 'not_analyzed'},
                    '600433': {'name': '冠豪高新', 'role': '特种纸/包装用纸', 'tag': 'not_analyzed'},
                },
            },
            '酿造装备': {
                'description': '糖化/发酵罐/灌装线等酿造装备',
                'companies': {
                    '603076': {'name': '乐惠国际', 'role': '国内啤酒装备龙头，青啤/华润/百威供货', 'tag': 'not_analyzed'},
                },
            },
            '原料（大麦/啤酒花/麦芽）': {
                'description': 'A 股直投标的稀缺，大麦/啤酒花主要从澳大利亚、法国、德国进口；关注进口成本波动',
                'companies': {},
            },
        },
        'midstream': {
            '区域啤酒品牌': {
                'description': '区域型啤酒品牌（核心 4 家已在 core/extra_cores）',
                'companies': {
                    '002461': {'name': '珠江啤酒', 'role': '华南区域龙头、高端 97 纯生', 'tag': 'not_analyzed'},
                    '000929': {'name': '兰州黄河', 'role': '西北区域啤酒', 'tag': 'not_analyzed'},
                },
            },
            '精酿/进口代理': {
                'description': '精酿啤酒兴起 + 进口品牌代理，A 股直投标的稀缺',
                'companies': {},
            },
        },
        'downstream': {
            '餐饮渠道': {'description': '啤酒消费 50%+ 来自餐饮，即饮/夜场是高端化主战场'},
            '商超电商': {'description': '商超/便利店/电商/即时零售，中高端线与家庭消费主场'},
            '体育赛事营销': {'description': '历届世界杯/欧洲杯啤酒赞助脉冲（联动 worldcup_2026）'},
            '出口海外': {'description': '青啤/华润出海，东南亚/北美/日韩市场'},
        },
        'competitors': {
            'BUD':       {'name': '百威英博', 'market': 'US'},
            '1876.HK':   {'name': '百威亚太', 'market': 'HK'},
            'TAP':       {'name': 'Molson Coors', 'market': 'US'},
            'HEINY':     {'name': 'Heineken', 'market': 'US'},
            'CARL-B.CO': {'name': '嘉士伯（重啤控股方）', 'market': 'EU'},
        },
        'trends': {
            'bandwidth': '销量见顶(2013) → 吨价高端化 → 超高端(1664/科罗娜/喜力)',
            'technologies': ['高端化结构', '精酿兴起', '即饮渠道数字化', 'CR5 寡头默契'],
            'china_role': 'CR5 主导：华润/青啤/百威亚太/燕京/嘉士伯占销量 ~90%',
        },
    },
}


def get_supply_chain(name):
    """获取指定供应链图谱"""
    return SUPPLY_CHAIN_GRAPHS.get(name)


def get_all_stock_codes(name):
    """提取供应链中所有股票代码"""
    graph = SUPPLY_CHAIN_GRAPHS.get(name)
    if not graph:
        return []

    codes = []
    # 核心公司
    if graph.get('code'):
        codes.append(graph['code'])

    # 额外核心（双核心/多核心产业链）
    for extra in graph.get('extra_cores', []) or []:
        if extra.get('code'):
            codes.append(extra['code'])

    # 上游/中游/下游（下游分类若含 companies 也收录）
    for stream in ('upstream', 'midstream', 'downstream'):
        for _category, info in graph.get(stream, {}).items():
            for code in info.get('companies', {}):
                codes.append(code)

    # 竞争对手
    for code in graph.get('competitors', {}):
        codes.append(code)

    return codes


def get_chain_summary(name):
    """生成供应链摘要文本"""
    graph = SUPPLY_CHAIN_GRAPHS.get(name)
    if not graph:
        return ''

    lines = [f"📊 *{graph['name']} ({graph['code']}) 产业链图谱*"]
    lines.append(f"定位: {graph['description']}")
    lines.append(f"核心技术: {', '.join(graph['core']['technologies'])}")
    lines.append(f"主要客户: {', '.join(graph['core']['customers'])}")
    lines.append('')

    for stream, label in [('upstream', '上游'), ('midstream', '中游')]:
        for category, info in graph.get(stream, {}).items():
            companies = info.get('companies', {})
            names = [f"{v['name']}({k})" for k, v in companies.items()]
            lines.append(f"*{label} - {category}*: {', '.join(names)}")

    lines.append('')
    lines.append(f"趋势: {graph['trends']['bandwidth']}")
    return '\n'.join(lines)

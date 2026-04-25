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
    'storage': {
        'name': 'SK海力士',
        'code': '000660.KS',
        'description': 'DRAM/HBM 全球第二 + AI 时代存储三大模块 + 国产替代',
        'core': {
            'technologies': ['DDR5', 'HBM3E/HBM4', '3D NAND', 'CXL 内存池化', '1a/1b nm DRAM'],
            'products': ['DRAM', 'HBM', 'NAND Flash', 'eSSD'],
            'customers': ['NVIDIA', 'AMD', '苹果', 'Google', 'Meta', '数据中心', '手机厂商'],
        },
        'extra_cores': [
            {
                'code': 'MU',
                'name': '美光',
                'market': 'US',
                'description': 'DRAM/NAND/HBM 三巨头之一，美国唯一存储大厂',
            },
            {
                'code': '005930.KS',
                'name': '三星电子',
                'market': 'KR',
                'description': 'DRAM/NAND 全球第一，HBM3E 追赶 SK海力士（行情仅展示）',
            },
            {
                'code': '285A.T',
                'name': '铠侠 Kioxia',
                'market': 'JP',
                'description': 'NAND 第二大厂（原东芝存储），2024 日本重新上市（行情仅展示）',
            },
            {
                'code': 'SNDK',
                'name': '闪迪 Sandisk',
                'market': 'US',
                'description': 'NAND 消费端龙头，2025 从西数分拆独立上市',
            },
            {
                'code': 'YMTC',
                'name': '长江存储',
                'market': 'CN',
                'description': '中国 3D NAND 唯一量产厂（未上市），Xtacking 架构',
            },
            {
                'code': 'CXMT',
                'name': '长鑫存储',
                'market': 'CN',
                'description': '中国 DRAM 唯一量产厂（未上市），DDR4/LPDDR4X 主力',
            },
        ],
        'upstream': {
            '半导体设备': {
                'description': '存储芯片制造核心设备（刻蚀/薄膜/CMP）',
                'companies': {
                    '002371': {'name': '北方华创', 'role': '刻蚀/薄膜沉积（存储产线核心，同属光通信/CPU 链）'},
                    '688012': {'name': '中微公司', 'role': '刻蚀设备（3D NAND 堆叠关键）'},
                    '688072': {'name': '拓荆科技', 'role': 'PECVD/ALD 薄膜沉积'},
                    '688120': {'name': '华海清科', 'role': 'CMP 抛光设备龙头'},
                },
            },
            '电子材料': {
                'description': '前驱体 / 光刻胶 / 特气 / CMP 抛光液',
                'companies': {
                    '002409': {'name': '雅克科技', 'role': '前驱体材料（存储刻蚀/薄膜必需）'},
                    '300054': {'name': '鼎龙股份', 'role': 'CMP 抛光垫/液国产替代'},
                    '688019': {'name': '安集科技', 'role': 'CMP 抛光液'},
                },
            },
            '硅片/衬底': {
                'description': '存储芯片基础衬底',
                'companies': {
                    '688126': {'name': '沪硅产业', 'role': '12 英寸大硅片国产替代'},
                    '002129': {'name': 'TCL中环', 'role': '半导体硅片 + 单晶硅'},
                },
            },
        },
        'midstream': {
            'DDR 内存接口': {
                'description': 'DDR5 服务器内存接口芯片 + DRAM 自研 + 车规 DRAM',
                'companies': {
                    '688008': {'name': '澜起科技', 'role': 'DDR5 RCD/DB 内存接口全球三强'},
                    '688123': {'name': '聚辰股份', 'role': 'DDR5 SPD EEPROM（澜起独家配套，SPD 全球三强）'},
                    '603986': {'name': '兆易创新', 'role': 'DRAM 自研 17nm DDR4 已量产（跨 DDR/NAND 双线）'},
                    '300223': {'name': '北京君正', 'role': '车规 DRAM/SRAM（ISSI）'},
                },
            },
            'HBM 先进封装': {
                'description': 'HBM 2.5D/3D 封装 + TSV + CoWoS 配套',
                'companies': {
                    '002156': {'name': '通富微电', 'role': 'AMD HBM 封装主力'},
                    '600584': {'name': '长电科技', 'role': '国内封测龙头，HBM 先进封装'},
                    '000021': {'name': '深科技', 'role': '金士顿合资，DRAM 封测'},
                    '600667': {'name': '太极实业', 'role': 'SK海力士 DRAM 封测合资（core 生态）'},
                },
            },
            'NAND 主控/颗粒': {
                'description': 'NAND 存储主控芯片 + NOR Flash + 小容量 DRAM',
                'companies': {
                    '688110': {'name': '东芯股份', 'role': 'SLC NAND / NOR / 小容量 DRAM'},
                    '603986': {'name': '兆易创新', 'role': 'NOR Flash 全球前三（跨 DDR/NAND 双线）'},
                    '688766': {'name': '普冉股份', 'role': 'NOR Flash / EEPROM'},
                    '688449': {'name': '联芸科技', 'role': 'SSD 主控芯片龙头'},
                    '300672': {'name': '国科微', 'role': '企业级 SSD 主控'},
                },
            },
            '存储模组': {
                'description': '消费级/企业级 SSD/eMMC/UFS 模组与品牌',
                'companies': {
                    '301308': {'name': '江波龙', 'role': 'DRAM/eMMC/UFS/SSD 模组龙头'},
                    '688525': {'name': '佰维存储', 'role': '嵌入式存储 + 企业级 SSD'},
                    '001309': {'name': '德明利', 'role': 'SSD/存储卡品牌 + 主控'},
                    '300042': {'name': '朗科科技', 'role': 'U盘/SSD 品牌（U盘发明专利持有者）'},
                },
            },
            '传统存储/HDD': {
                'description': '企业级 HDD（云冷数据主力）+ 磁存储配套，A 股无直投标的，核心玩家见 competitors（WDC / STX）',
                'companies': {},
            },
        },
        'downstream': {
            'AI 服务器/HBM': {'description': 'HBM3E/HBM4 + DDR5 RDIMM，AI 训练推理主战场'},
            '消费电子': {'description': '手机/PC/平板 DRAM+NAND'},
            '企业级存储': {'description': '数据中心 QLC SSD + HDD 冷存储 + CXL 内存池'},
            '汽车电子': {'description': '车规存储（ADAS/智能座舱/自动驾驶）'},
        },
        'competitors': {
            'MU':        {'name': '美光', 'market': 'US'},
            '005930.KS': {'name': '三星电子', 'market': 'KR'},
            '285A.T':    {'name': '铠侠 Kioxia', 'market': 'JP'},
            'SNDK':      {'name': '闪迪 Sandisk', 'market': 'US'},
            'WDC':       {'name': '西部数据', 'market': 'US'},
            'STX':       {'name': '希捷科技', 'market': 'US'},
        },
        'trends': {
            'bandwidth': 'DDR4→DDR5→DDR6 / HBM3→HBM3E→HBM4 16 层堆叠',
            'technologies': ['HBM4 16 层堆叠', '3D NAND 300+ 层', 'CXL 内存池化',
                             'QLC 企业 SSD', '1b nm DRAM'],
            'china_role': '长江/长鑫追赶量产 + 模组封测全栈 + NOR/小容量 DRAM 自主',
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
    'nvidia': {
        'name': 'NVIDIA',
        'code': 'NVDA',
        'description': '全球 AI GPU 算力绝对龙头 + A 股间接供应链（服务器 ODM / PCB / 光模块 / 液冷）',
        'core': {
            'technologies': ['Blackwell B200/GB200', 'Hopper H100/H200', 'CUDA',
                             'NVLink/NVSwitch', 'Spectrum-X', 'Grace CPU', 'CoWoS-L 封装'],
            'products': ['AI 训练 GPU', 'AI 推理 GPU', 'DGX/HGX 系统',
                         'NVLink Switch', 'BlueField DPU', 'Spectrum-X 以太网'],
            'customers': ['微软/Meta/Google/AWS/Oracle/xAI', '戴尔/超微/联想/HPE 服务器 OEM',
                          '中国云厂商（合规版 H20/B30A）'],
        },
        'upstream': {
            'PCB / CCL': {
                'description': 'AI 服务器高多层 PCB / HDI / FC-BGA 基板 / 覆铜板',
                'companies': {
                    '002463': {'name': '沪电股份', 'role': 'AI 服务器高多层 PCB 龙头（同属 ascend 产业链）', 'tag': 'not_analyzed'},
                    '300476': {'name': '胜宏科技', 'role': 'NVIDIA GB200 PCB 主力供应商', 'tag': 'not_analyzed'},
                    '600183': {'name': '生益科技', 'role': '高频高速覆铜板（同属 ascend 产业链）', 'tag': 'not_analyzed'},
                    '002916': {'name': '深南电路', 'role': 'FC-BGA 基板 / 通信 PCB（同属 cpu/ascend 产业链）', 'tag': 'not_analyzed'},
                    '002436': {'name': '兴森科技', 'role': 'FC-BGA 基板 / IC 载板（同属 cpu 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '连接器 / 铜缆': {
                'description': '高速铜缆 / AI 高速背板连接器（NVLink Scale-up 互连）',
                'companies': {
                    '002130': {'name': '沃尔核材', 'role': '高速铜缆 / OAM Scale-up 互连', 'tag': 'not_analyzed'},
                    '688668': {'name': '鼎通科技', 'role': 'AI 高速背板连接器', 'tag': 'not_analyzed'},
                    '300252': {'name': '金信诺', 'role': '高速线缆组件', 'tag': 'not_analyzed'},
                },
            },
            '光模块 / 光芯片': {
                'description': 'Scale-out 800G/1.6T 光互连',
                'companies': {
                    '300308': {'name': '中际旭创', 'role': '800G/1.6T 光模块龙头（同属 ascend/lumentum 产业链）', 'tag': 'not_analyzed'},
                    '300502': {'name': '新易盛', 'role': '800G 光模块（同属 ascend/lumentum 产业链）', 'tag': 'not_analyzed'},
                    '300394': {'name': '天孚通信', 'role': 'CPO 光引擎 / 连接器（同属 ascend/lumentum 产业链）', 'tag': 'not_analyzed'},
                    '002281': {'name': '光迅科技', 'role': '光芯片 EML/DFB（同属 ascend/lumentum 产业链）', 'tag': 'not_analyzed'},
                    '000988': {'name': '华工科技', 'role': '光模块 / 激光（同属 ascend/lumentum 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '液冷 / 散热': {
                'description': 'AI 服务器液冷冷板 + 精密空调',
                'companies': {
                    '002837': {'name': '英维克', 'role': '数据中心液冷龙头（同属 ascend 产业链）', 'tag': 'not_analyzed'},
                    '300499': {'name': '高澜股份', 'role': '液冷温控（同属 ascend 产业链）', 'tag': 'not_analyzed'},
                    '300602': {'name': '飞荣达', 'role': '导热散热材料（同属 ascend 产业链）', 'tag': 'not_analyzed'},
                    '301018': {'name': '申菱环境', 'role': '数据中心精密空调', 'tag': 'not_analyzed'},
                },
            },
            '封测（CoWoS/HBM 辅助）': {
                'description': '先进封装与 Chiplet（台积电 CoWoS 主导，A 股参与辅助段）',
                'companies': {
                    '600584': {'name': '长电科技', 'role': '全球前三封测，Chiplet 高端封装（同属 cpu 产业链）', 'tag': 'not_analyzed'},
                    '002156': {'name': '通富微电', 'role': 'AMD/NVIDIA GPU 封测（同属 cpu 产业链）', 'tag': 'not_analyzed'},
                    '002185': {'name': '华天科技', 'role': '国内第三大封测（同属 cpu 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '电源模组': {
                'description': 'AI 服务器高功率电源',
                'companies': {
                    '002851': {'name': '麦格米特', 'role': 'AI 服务器电源模组', 'tag': 'not_analyzed'},
                    '300870': {'name': '欧陆通', 'role': '服务器电源', 'tag': 'not_analyzed'},
                },
            },
        },
        'midstream': {
            'AI 服务器 ODM / 品牌': {
                'description': 'NVIDIA HGX/DGX 平台服务器代工与国内合规版品牌',
                'companies': {
                    '601138': {'name': '工业富联', 'role': '全球最大 NVIDIA AI 服务器代工（同属 cpu/ascend 产业链）', 'tag': 'not_analyzed'},
                    '000977': {'name': '浪潮信息', 'role': '国内 NVIDIA 服务器主力（H20/B30A）', 'tag': 'not_analyzed'},
                    '000938': {'name': '紫光股份', 'role': '新华三，企业级 NV 服务器', 'tag': 'not_analyzed'},
                    '603019': {'name': '中科曙光', 'role': '国产算力 + NV 兼容服务器（同属 ascend 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '网络交换机': {
                'description': '数据中心高端交换机（NVIDIA Spectrum-X 生态配套）',
                'companies': {
                    '002396': {'name': '星网锐捷', 'role': '高端数据中心交换机', 'tag': 'not_analyzed'},
                    '301191': {'name': '菲菱科思', 'role': '交换机 ODM', 'tag': 'not_analyzed'},
                },
            },
        },
        'downstream': {
            'AI 数据中心': {'description': '北美四大云 + 国内互联网智算中心'},
            '大模型训练推理': {'description': '全球主流大模型（OpenAI/Anthropic/xAI/Meta/Google）+ 国内合规版需求'},
            '自动驾驶 / 车载': {
                'description': 'NV Orin/Thor 平台上车',
                'companies': {
                    '002920': {'name': '德赛西威', 'role': 'NV Orin/Thor 域控合作', 'tag': 'not_analyzed'},
                    '600699': {'name': '均胜电子', 'role': 'NV 智驾域控合作', 'tag': 'not_analyzed'},
                },
            },
            '机器人 / 具身智能': {
                'description': 'NV Isaac/GR00T 生态',
                'companies': {
                    '002747': {'name': '埃斯顿', 'role': '工业机器人国产龙头 + 具身智能', 'tag': 'not_analyzed'},
                    '002050': {'name': '三花智控', 'role': '人形机器人执行器 + 热管理', 'tag': 'not_analyzed'},
                },
            },
        },
        'competitors': {
            'TSM':       {'name': '台积电', 'market': 'US'},
            'AVGO':      {'name': '博通', 'market': 'US'},
            'AMD':       {'name': 'AMD', 'market': 'US'},
            'INTC':      {'name': 'Intel', 'market': 'US'},
            '000660.KS': {'name': 'SK 海力士', 'market': 'KR'},
            'MU':        {'name': '美光', 'market': 'US'},
            '005930.KS': {'name': '三星电子', 'market': 'KR'},
            '688256':    {'name': '寒武纪', 'market': 'A'},
            '688041':    {'name': '海光信息', 'market': 'A'},
        },
        'trends': {
            'bandwidth': 'H100 → H200 → B200 → B300 → Rubin(2026)',
            'technologies': ['NVLink 超节点', 'Blackwell/Rubin 架构', 'Spectrum-X 以太网',
                             'CoWoS-L 封装', '液冷冷板 + 浸没式'],
            'china_role': '服务器 ODM（工业富联/浪潮）+ PCB（沪电/胜宏）+ 光模块（旭创/新易盛）'
                          '+ 液冷（英维克）+ 封测（长电/通富）全链条深度供应',
        },
    },
    'energy_storage': {
        'name': '宁德时代',
        'code': '300750',
        'description': '全球储能/动力电池龙头 + A 股储能全产业链（电芯/PCS/集成/温控）',
        'core': {
            'technologies': ['磷酸铁锂', '280Ah/314Ah 大电芯', 'CTP/CTC 无模组',
                             '液冷热管理', '构网型 PCS', '钠离子电池'],
            'products': ['储能电芯', 'Pack', '储能系统 EnerOne/EnerC', '动力电池', '换电'],
            'customers': ['电网公司', '新能源电站', '户储欧美', '工商业园区', '车企'],
        },
        'extra_cores': [
            {
                'code': '300274',
                'name': '阳光电源',
                'market': 'A',
                'description': 'PCS + 储能系统集成全球 Top，光储充一体化出海龙头',
            },
            {
                'code': '002594',
                'name': '比亚迪',
                'market': 'A',
                'description': '刀片电池 + 储能集成，垂直一体化新能源龙头',
            },
            {
                'code': '300014',
                'name': '亿纬锂能',
                'market': 'A',
                'description': '储能电芯第二梯队，280Ah/314Ah 大电芯主力',
            },
            {
                'code': '688063',
                'name': '派能科技',
                'market': 'A',
                'description': '户储电池龙头，欧洲户储高份额',
            },
        ],
        'upstream': {
            '锂盐 / 正极材料': {
                'description': '锂资源 + 磷酸铁锂/三元正极 + 前驱体',
                'companies': {
                    '002460': {'name': '赣锋锂业', 'role': '锂盐全球龙头 + 固态电池布局', 'tag': 'not_analyzed'},
                    '002466': {'name': '天齐锂业', 'role': '锂资源自给率全球第一', 'tag': 'not_analyzed'},
                    '300769': {'name': '德方纳米', 'role': '磷酸铁锂正极龙头（宁德核心供应）', 'tag': 'not_analyzed'},
                    '300073': {'name': '当升科技', 'role': '高镍三元正极 + 磷酸铁锂', 'tag': 'not_analyzed'},
                    '300919': {'name': '中伟股份', 'role': '三元前驱体全球龙头', 'tag': 'not_analyzed'},
                    '603799': {'name': '华友钴业', 'role': '钴镍资源 + 三元前驱体', 'tag': 'not_analyzed'},
                },
            },
            '负极材料': {
                'description': '人造石墨 / 天然石墨 / 硅基负极',
                'companies': {
                    '835185': {'name': '贝特瑞', 'role': '负极材料全球第一（北交所）', 'tag': 'not_analyzed'},
                    '300035': {'name': '中科电气', 'role': '人造石墨负极', 'tag': 'not_analyzed'},
                    '603659': {'name': '璞泰来', 'role': '负极 + 涂覆隔膜双主业', 'tag': 'not_analyzed'},
                },
            },
            '电解液': {
                'description': '电解液 + 六氟磷酸锂 + 添加剂',
                'companies': {
                    '002709': {'name': '天赐材料', 'role': '电解液全球第一（宁德核心供应）', 'tag': 'not_analyzed'},
                    '300037': {'name': '新宙邦', 'role': '电解液第二 + 氟化工', 'tag': 'not_analyzed'},
                    '002407': {'name': '多氟多', 'role': '六氟磷酸锂龙头', 'tag': 'not_analyzed'},
                },
            },
            '隔膜': {
                'description': '湿法/干法隔膜 + 陶瓷涂覆',
                'companies': {
                    '002812': {'name': '恩捷股份', 'role': '湿法隔膜全球第一', 'tag': 'not_analyzed'},
                    '300568': {'name': '星源材质', 'role': '干法+湿法隔膜双线', 'tag': 'not_analyzed'},
                },
            },
            '结构件与铜箔': {
                'description': '电池壳体 / 铝塑膜 / 锂电铜箔',
                'companies': {
                    '002850': {'name': '科达利', 'role': '动力/储能电池结构件龙头', 'tag': 'not_analyzed'},
                    '300129': {'name': '泰胜风能', 'role': '储能结构件配套（风储联动）', 'tag': 'not_analyzed'},
                },
            },
        },
        'midstream': {
            '储能电芯与 Pack': {
                'description': '方形/圆柱储能电芯 + Pack 组装',
                'companies': {
                    '002074': {'name': '国轩高科', 'role': '大众入股，储能电芯第二梯队', 'tag': 'not_analyzed'},
                    '300207': {'name': '欣旺达', 'role': '动力+储能电芯 + 消费电池龙头', 'tag': 'not_analyzed'},
                    '300750': {'name': '宁德时代', 'role': 'core 自身（EnerOne/EnerC 储能系统）'},
                },
            },
            'BMS / PCS / 逆变器': {
                'description': '电池管理系统 + 储能变流器 + 逆变器',
                'companies': {
                    '300693': {'name': '盛弘股份', 'role': 'PCS 储能变流器专业龙头', 'tag': 'not_analyzed'},
                    '300827': {'name': '上能电气', 'role': 'PCS + 光伏逆变器', 'tag': 'not_analyzed'},
                    '688390': {'name': '固德威', 'role': '户储逆变器 + PCS 出海', 'tag': 'not_analyzed'},
                    '300763': {'name': '锦浪科技', 'role': '组串/储能逆变器出海', 'tag': 'not_analyzed'},
                },
            },
            '储能系统集成': {
                'description': '电站级储能集成 + EPC + 光储充一体化',
                'companies': {
                    '600406': {'name': '国电南瑞', 'role': '电网侧储能 + 调度系统龙头', 'tag': 'not_analyzed'},
                    '002028': {'name': '思源电气', 'role': '电网设备 + 储能变流器', 'tag': 'not_analyzed'},
                    '688408': {'name': '中信博', 'role': '跟踪支架 + 储能集成', 'tag': 'not_analyzed'},
                },
            },
            '温控与消防': {
                'description': '液冷/风冷热管理 + 锂电消防方案',
                'companies': {
                    '002837': {'name': '英维克', 'role': '液冷热管理龙头（数据中心+储能双驱）', 'tag': 'not_analyzed'},
                    '300499': {'name': '高澜股份', 'role': '储能液冷专业供应商', 'tag': 'not_analyzed'},
                    '002009': {'name': '天奇股份', 'role': '锂电池消防 + 电池回收', 'tag': 'not_analyzed'},
                },
            },
        },
        'downstream': {
            '电网侧储能': {'description': '调峰调频 + 共享储能电站，2024-2030 国内装机主战场'},
            '工商业储能': {'description': '峰谷套利 + 需量管理，经济性敏感但增速快'},
            '户用储能': {'description': '欧洲/美澳/日本户储，派能/比亚迪/华为出海主力'},
            '新能源配储': {'description': '风电/光伏强制配储 10-30% / 2-4h，装机刚性支撑'},
            '充电桩与换电': {'description': '光储充一体化 + 换电站，车网互动(V2G)前瞻'},
        },
        'competitors': {
            '373220.KS': {'name': 'LG 新能源', 'market': 'KR'},
            'TSLA':      {'name': '特斯拉 Megapack', 'market': 'US'},
            'FLNC':      {'name': 'Fluence Energy', 'market': 'US'},
            'ENPH':      {'name': 'Enphase Energy', 'market': 'US'},
            '6752.T':    {'name': '松下 Panasonic', 'market': 'JP'},
        },
        'trends': {
            'bandwidth': '280Ah → 314Ah → 500Ah+ 大电芯 / 2h → 4h → 8h+ 长时储能',
            'technologies': ['磷酸铁锂主流', '钠离子电池量产', '液冷热管理',
                             '构网型 PCS', '长时储能(液流/压缩空气)', '固态电池'],
            'china_role': '电芯产能全球 80%+ / PCS 与集成出海（阳光/宁德/比亚迪三强领跑欧美）'
                          '/ 四大材料（正极/负极/电解液/隔膜）全球绝对主导',
        },
    },
    'copper': {
        'name': '铜产业链',
        'code': 'COPPER',
        'description': '电气化时代核心金属：能源转型 + AI 数据中心 + 电网升级三轮驱动',
        'core': {
            'technologies': ['湿法/火法冶炼', '阳极泥提金', '电解精炼', '锂电铜箔', '高速铜缆'],
            'products': ['铜精矿', '阴极铜（电解铜）', '铜杆/铜管/铜带', '锂电铜箔', '漆包线'],
            'customers': ['国家电网', '新能源车', '储能电站', 'AI 数据中心', '空调家电', '建筑'],
        },
        'extra_cores': [
            {
                'code': '601899',
                'name': '紫金矿业',
                'market': 'A',
                'description': '全球前十铜矿商 + 国内最大金铜矿龙头（Don Buy：当前估值偏高）',
            },
            {
                'code': '603993',
                'name': '洛阳钼业',
                'market': 'A',
                'description': '刚果金 TFM/KFM 铜钴双矿主力（Don Buy：仅极端低估才考虑）',
            },
            {
                'code': '600362',
                'name': '江西铜业',
                'market': 'A',
                'description': '国内最大纯铜业（自有矿+冶炼），A 股铜价 β 代表',
            },
            {
                'code': '000630',
                'name': '铜陵有色',
                'market': 'A',
                'description': '国内第二大铜冶炼，安徽国资',
            },
        ],
        'upstream': {
            '铜矿资源': {
                'description': '国内/海外铜精矿自给主力（自给率约 20%，海外并购为主）',
                'companies': {
                    '601899': {'name': '紫金矿业', 'role': '全球前十铜矿商，金铜兼营（同 extra_cores）', 'tag': 'don_buy'},
                    '603993': {'name': '洛阳钼业', 'role': '刚果金 TFM/KFM 铜钴双矿（同 extra_cores）', 'tag': 'don_buy'},
                    '600362': {'name': '江西铜业', 'role': '国内最大铜矿+冶炼一体化（同 extra_cores）'},
                    '601168': {'name': '西部矿业', 'role': '玉龙铜矿 + 铜锌铅多金属', 'tag': 'not_analyzed'},
                    '600489': {'name': '中金黄金', 'role': '黄金为主、铜为辅，金铜伴生（Don Buy）', 'tag': 'don_buy'},
                },
            },
            '铜冶炼': {
                'description': '阴极铜（电解铜）冶炼龙头，全球产能 45%+ 集中于中国',
                'companies': {
                    '000630': {'name': '铜陵有色', 'role': '国内第二大铜冶炼，安徽国资（同 extra_cores）'},
                    '000878': {'name': '云南铜业', 'role': '国内第三大铜冶炼，西南龙头', 'tag': 'not_analyzed'},
                },
            },
            '副产物（金/钴/钼）': {
                'description': '铜矿伴生贵金属与小金属，副产物贡献毛利',
                'companies': {
                    '600489': {'name': '中金黄金', 'role': '金铜兼营，铜为副产（Don Buy 同上）', 'tag': 'don_buy'},
                    '603993': {'name': '洛阳钼业', 'role': '刚果金钴副产 + 钼业务（同上 Don Buy）', 'tag': 'don_buy'},
                },
            },
            '矿山装备': {
                'description': '选矿/破碎/电解槽设备，A 股直投标的稀缺',
                'companies': {},
            },
        },
        'midstream': {
            '铜管/铜杆': {
                'description': '空调铜管 + 电力铜杆，全球出口龙头',
                'companies': {
                    '002203': {'name': '海亮股份', 'role': '全球铜管第一，空调/制冷主力', 'tag': 'not_analyzed'},
                    '002295': {'name': '精艺股份', 'role': '精密铜管', 'tag': 'not_analyzed'},
                },
            },
            '铜带/铜板/合金': {
                'description': '高端铜合金 + 铜带（连接器/引线框架/汽车端子）',
                'companies': {
                    '002171': {'name': '楚江新材', 'role': '铜带龙头 + 锂电铜箔', 'tag': 'not_analyzed'},
                    '601137': {'name': '博威合金', 'role': '高端铜合金（汽车/通信连接器）', 'tag': 'not_analyzed'},
                    '601609': {'name': '金田股份', 'role': '综合铜加工龙头', 'tag': 'not_analyzed'},
                    '600255': {'name': '鑫科材料', 'role': '铜基新材料', 'tag': 'not_analyzed'},
                },
            },
            '锂电铜箔': {
                'description': '4-8μm 极薄铜箔（动力/储能电池负极集流体）',
                'companies': {
                    '600110': {'name': '诺德股份', 'role': '锂电铜箔龙头（同属 energy_storage 链）', 'tag': 'not_analyzed'},
                    '002171': {'name': '楚江新材', 'role': '铜带 + 锂电铜箔双线（同上）', 'tag': 'not_analyzed'},
                },
            },
        },
        'downstream': {
            '电力电网': {
                'description': '特高压电缆 + 变压器铜绕组，电网投资刚性需求',
                'companies': {
                    '600406': {'name': '国电南瑞', 'role': '电网调度 + 储能（同属 energy_storage 产业链）', 'tag': 'not_analyzed'},
                    '002028': {'name': '思源电气', 'role': '变压器/开关 + 储能变流器（同属 energy_storage 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '新能源车 / 储能': {
                'description': '电池铜箔 + 结构件 + 高压线束，单车铜含量 60kg vs 燃油车 23kg',
                'companies': {
                    '300750': {'name': '宁德时代', 'role': '动力/储能电池龙头（同属 energy_storage core）'},
                    '002850': {'name': '科达利', 'role': '电池结构件铜部件（同属 energy_storage 产业链）', 'tag': 'not_analyzed'},
                },
            },
            'AI 数据中心': {
                'description': 'NVLink Scale-up 高速铜缆 + 高速背板连接器（铜缆部分替代光模块）',
                'companies': {
                    '002130': {'name': '沃尔核材', 'role': '高速铜缆 / OAM Scale-up 互连（同属 nvidia 产业链）', 'tag': 'not_analyzed'},
                    '688668': {'name': '鼎通科技', 'role': 'AI 高速背板连接器（同属 nvidia 产业链）', 'tag': 'not_analyzed'},
                    '300252': {'name': '金信诺', 'role': '高速线缆组件（同属 nvidia 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '空调家电 / 建筑': {
                'description': '家电铜管 + 建筑布线，A 股集中度低，主供应方见 midstream（海亮/精艺）',
                'companies': {},
            },
        },
        'competitors': {
            'FCX':     {'name': 'Freeport-McMoRan', 'market': 'US'},
            'SCCO':    {'name': 'Southern Copper', 'market': 'US'},
            'BHP':     {'name': '必和必拓', 'market': 'US'},
            'RIO':     {'name': '力拓', 'market': 'US'},
            '1208.HK': {'name': '五矿资源', 'market': 'HK'},
            '0358.HK': {'name': '江西铜业(H)', 'market': 'HK'},
        },
        'trends': {
            'bandwidth': '铜价 USD/t：2020 5000 → 2024 9500 → 2030E 12000+（IEA 长期短缺）',
            'technologies': ['锂电铜箔 6μm→4μm 极薄化', 'AI 数据中心高速铜缆替代部分光模块',
                             '电网特高压扩张', '新能源车单车铜含量 60kg vs 燃油车 23kg'],
            'china_role': '冶炼产能全球 45%+ / 铜矿自给率仅 20%（紫金/洛阳钼业海外并购主力）'
                          ' / 铜加工（海亮/楚江/博威）出口竞争力全球前列',
        },
    },
    'apple': {
        'name': '苹果',
        'code': 'AAPL',
        'description': '全球消费电子绝对龙头，A 股苹果链覆盖玻璃/声学/光学/FPC/结构件/组装全栈',
        'core': {
            'technologies': ['Apple Silicon (A/M 系列)', 'iOS/macOS/visionOS',
                             'MicroLED', 'OLED LTPO', '钛金属机身', 'UWB/U2 芯片',
                             'Face ID 3D 结构光', 'Apple Intelligence 端侧 AI'],
            'products': ['iPhone', 'Mac', 'iPad', 'AirPods', 'Apple Watch',
                         'Vision Pro', 'Services（App Store/iCloud/广告）'],
            'customers': ['全球高端消费电子用户', '企业 IT', '开发者生态', '运营商渠道'],
        },
        'upstream': {
            '玻璃盖板与外观件': {
                'description': 'iPhone/Watch/Vision Pro 前后盖玻璃 + 触控显示模组',
                'companies': {
                    '300433': {'name': '蓝思科技', 'role': '苹果玻璃盖板核心供应（iPhone/Watch）', 'tag': 'not_analyzed'},
                    '300088': {'name': '长信科技', 'role': '触控显示模组 + 玻璃减薄', 'tag': 'not_analyzed'},
                    '603876': {'name': '鼎胜新材', 'role': '苹果电池铝箔配套', 'tag': 'not_analyzed'},
                },
            },
            '光学摄像头': {
                'description': 'iPhone 多摄模组 + 镜头 + VCSEL 3D 传感',
                'companies': {
                    '002456': {'name': '欧菲光', 'role': '前置摄像/触控（曾被剔除后部分回归）', 'tag': 'don_buy'},
                    '600703': {'name': '三安光电', 'role': 'VCSEL/磷化铟（同属 lumentum 产业链）', 'tag': 'frontEC'},
                },
            },
            'PCB / FPC': {
                'description': '主板 HDI / SLP + 模组 FPC（iPhone/Watch/AirPods）',
                'companies': {
                    '002938': {'name': '鹏鼎控股', 'role': '苹果 FPC 全球第一供应（iPhone 主板/电池/无线充）', 'tag': 'not_analyzed'},
                    '002384': {'name': '东山精密', 'role': 'Apple Watch FPC + iPhone 天线', 'tag': 'not_analyzed'},
                    '002463': {'name': '沪电股份', 'role': '高多层 PCB（同属 ascend/nvidia 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '声学元件': {
                'description': 'AirPods/iPhone 麦克风/扬声器/振动马达',
                'companies': {
                    '002241': {'name': '歌尔股份', 'role': 'AirPods 主力组装 + Vision Pro 独家代工', 'tag': 'not_analyzed'},
                    '2018.HK': {'name': '瑞声科技', 'role': '声学/触觉马达/光学，苹果声学双供之一', 'tag': 'not_analyzed'},
                },
            },
            '连接器与精密结构件': {
                'description': 'Lightning/USB-C/MagSafe 连接器 + iPhone/Mac 金属中框/小件',
                'companies': {
                    '002475': {'name': '立讯精密', 'role': 'AirPods 主力组装 + iPhone 部分组装 + 连接器', 'tag': 'not_analyzed'},
                    '300115': {'name': '长盈精密', 'role': 'iPhone 金属结构件 + Apple Watch 表壳', 'tag': 'not_analyzed'},
                    '002635': {'name': '安洁科技', 'role': 'iPhone/Mac 精密功能件、无线充模组', 'tag': 'not_analyzed'},
                },
            },
            '电池与电源': {
                'description': 'iPhone/Watch/AirPods 锂电池 Pack + 充电模块',
                'companies': {
                    '000049': {'name': '德赛电池', 'role': 'iPhone/Watch 电池 Pack 主力', 'tag': 'not_analyzed'},
                    '300207': {'name': '欣旺达', 'role': '苹果 iPhone/Mac 电池 Pack（同属 energy_storage 产业链）', 'tag': 'not_analyzed'},
                },
            },
            '显示面板': {
                'description': 'iPhone/iPad OLED/LTPO 面板（韩厂主导，国内 BOE 切入）',
                'companies': {
                    '000725': {'name': '京东方A', 'role': 'iPhone OLED 第三供应（追赶三星/LGD）', 'tag': 'not_analyzed'},
                    '000100': {'name': 'TCL科技', 'role': '中尺寸 LCD/Mini-LED 切入苹果备选', 'tag': 'not_analyzed'},
                },
            },
        },
        'midstream': {
            '整机组装 EMS/ODM': {
                'description': 'iPhone/Mac/iPad/AirPods/Vision Pro 组装代工',
                'companies': {
                    '601138': {'name': '工业富联', 'role': 'iPhone/Mac/iPad 全球最大代工（同属 cpu/ascend/nvidia 产业链）', 'tag': 'not_analyzed'},
                    '002475': {'name': '立讯精密', 'role': 'AirPods 主力 + iPhone 部分组装（同上 upstream）', 'tag': 'not_analyzed'},
                    '002241': {'name': '歌尔股份', 'role': 'AirPods + Vision Pro 独家组装（同上 upstream）', 'tag': 'not_analyzed'},
                    '0285.HK': {'name': '比亚迪电子', 'role': 'iPad/Mac 组装 + 金属中框', 'tag': 'not_analyzed'},
                },
            },
            '模组半成品': {
                'description': '摄像头模组、无线充模组、Touch ID/Face ID 模组',
                'companies': {
                    '2382.HK': {'name': '舜宇光学', 'role': '苹果摄像头模组主力', 'tag': 'not_analyzed'},
                    '1478.HK': {'name': '丘钛科技', 'role': '苹果摄像头模组备选', 'tag': 'not_analyzed'},
                },
            },
        },
        'downstream': {
            'iPhone': {'description': '苹果营收支柱（占比 ~50%），全球高端智能手机龙头'},
            'Mac': {'description': 'Apple Silicon 重塑 PC，M 系列芯片驱动产品力'},
            'iPad': {'description': '平板市场份额第一，教育/创作场景'},
            'AirPods': {'description': 'TWS 耳机绝对龙头，立讯/歌尔国内独享代工'},
            'Apple Watch': {'description': '智能手表全球第一，健康/医疗场景延展'},
            'Vision Pro': {'description': '空间计算新品类（2024 上市），歌尔独家代工'},
            'Services': {'description': 'App Store/iCloud/Apple Music/广告，毛利率 70%+ 第二增长曲线'},
        },
        'competitors': {
            '005930.KS': {'name': '三星电子', 'market': 'KR'},
            '1810.HK':   {'name': '小米集团', 'market': 'HK'},
            'GOOGL':     {'name': 'Alphabet/Google (Pixel)', 'market': 'US'},
            'MSFT':      {'name': 'Microsoft (Surface)', 'market': 'US'},
            'META':      {'name': 'Meta (Quest VR)', 'market': 'US'},
        },
        'trends': {
            'bandwidth': 'iPhone 销量见顶 → Services 接棒 → Vision Pro/AI 新增量（Apple Intelligence）',
            'technologies': ['Apple Silicon 自研芯片下沉到 iPhone/Mac/Vision Pro 全线',
                             'Vision Pro 空间计算开启', 'Apple Intelligence 端侧 AI',
                             'MicroLED/折叠屏路线探索', '印度产能扩张（去中国化）'],
            'china_role': '组装端：立讯/歌尔/工业富联三强主导；零部件端：蓝思（玻璃）/鹏鼎（FPC）'
                          '/京东方（OLED 切入）/德赛（电池）/长盈（结构件）全栈配套；'
                          '风险：印度/越南产能转移持续推进',
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

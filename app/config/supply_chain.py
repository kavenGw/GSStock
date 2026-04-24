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

    # 上游/中游
    for stream in ('upstream', 'midstream'):
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

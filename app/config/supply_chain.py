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

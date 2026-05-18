"""一次性迁移映射：buffett 文件名 -> (sector, subsector)。
Stage 1 用，Stage 5 删除。
"""
SECTOR_MAPPING: dict[str, tuple[str, str]] = {
    # ===== semiconductor =====
    '中芯国际': ('semiconductor', 'foundry'),
    '华虹半导体': ('semiconductor', 'foundry'),
    '兆易创新': ('semiconductor', 'storage'),
    '北京君正': ('semiconductor', 'storage'),
    '普冉股份': ('semiconductor', 'storage'),
    '江波龙': ('semiconductor', 'storage'),
    '聚辰股份': ('semiconductor', 'storage'),
    '复旦微电': ('semiconductor', 'storage'),
    '中颖电子': ('semiconductor', 'mcu'),
    '大普微': ('semiconductor', 'storage'),
    '长鑫科技': ('semiconductor', 'storage'),
    '太极实业': ('semiconductor', 'storage'),
    '长电科技': ('semiconductor', 'packaging'),
    '通富微电': ('semiconductor', 'packaging'),
    '华天科技': ('semiconductor', 'packaging'),
    '深科技': ('semiconductor', 'packaging'),
    '盛合晶微': ('semiconductor', 'packaging'),
    '国芯科技': ('semiconductor', 'design'),
    '希荻微': ('semiconductor', 'design'),
    '全志科技': ('semiconductor', 'design'),
    '芯原股份': ('semiconductor', 'design'),
    '中微公司': ('semiconductor', 'equipment'),
    '赛腾股份': ('semiconductor', 'equipment'),
    '彤程新材': ('semiconductor', 'materials'),
    '南大光电': ('semiconductor', 'materials'),
    '巨化股份': ('semiconductor', 'materials'),
    '昊华化学': ('semiconductor', 'materials'),
    '石英股份': ('semiconductor', 'materials'),
    '西部材料': ('semiconductor', 'materials'),
    '雅克科技': ('semiconductor', 'materials'),
    '中巨芯': ('semiconductor', 'materials'),
    '宏和科技': ('semiconductor', 'materials'),
    '圣泉集团': ('semiconductor', 'materials'),
    '江丰电子': ('semiconductor', 'materials'),
    '沪电股份': ('semiconductor', 'pcb'),
    '南亚新材': ('semiconductor', 'pcb'),
    '金安国纪': ('semiconductor', 'pcb'),
    '生益科技': ('semiconductor', 'pcb'),
    '兴森科技': ('semiconductor', 'pcb'),
    '胜宏科技': ('semiconductor', 'pcb'),
    '光迅科技': ('semiconductor', 'optical'),
    '光库科技': ('semiconductor', 'optical'),
    '源杰科技': ('semiconductor', 'optical'),
    '烽火通信': ('semiconductor', 'optical'),
    '迈威尔科技': ('semiconductor', 'design'),

    # ===== electronics =====
    '工业富联': ('electronics', 'ems'),
    '立讯精密': ('electronics', 'ems'),
    '鸿博股份': ('electronics', 'consumer'),
    '三花智控': ('electronics', 'components'),

    # ===== consumer =====
    '青岛啤酒': ('consumer', 'beer'),
    '重庆啤酒': ('consumer', 'beer'),
    '燕京啤酒': ('consumer', 'beer'),
    '安踏体育': ('consumer', 'sportswear'),
    '舒华体育': ('consumer', 'sportswear'),
    '金陵体育': ('consumer', 'sportswear'),
    '中体产业': ('consumer', 'sportswear'),
    '共创草坪': ('consumer', 'sportswear'),

    # ===== materials =====
    '万华化学': ('materials', 'chemicals'),
    '中国铝业': ('materials', 'nonferrous'),
    '云铝股份': ('materials', 'nonferrous'),
    '南山铝业': ('materials', 'nonferrous'),
    '天山铝业': ('materials', 'nonferrous'),
    '紫金矿业': ('materials', 'nonferrous'),
    '洛阳钼业': ('materials', 'nonferrous'),
    '盛屯矿业': ('materials', 'nonferrous'),
    '中金黄金': ('materials', 'nonferrous'),
    '盛达资源': ('materials', 'nonferrous'),
    '西部矿业': ('materials', 'nonferrous'),

    # ===== energy =====
    '阳光电源': ('energy', 'solar'),

    # ===== healthcare =====
    '药明康德': ('healthcare', 'cro'),

    # ===== media =====
    '粤传媒': ('media', 'advertising'),

    # ===== financial =====
    '东吴证券': ('financial', 'securities'),

    # ===== ai-application =====
    '甲骨文': ('ai-application', 'database'),
}

# 文件名匹配 -> 目标顶层目录。优先于 SECTOR_MAPPING 匹配（多股 / 主题 / 板块）。
SPECIAL_FILES: dict[str, str] = {
    # docs/analysis/ 根的多股专题 / 主题
    '光迅科技-光库科技': 'cross-sector',
    '工业富联-甲骨文': 'cross-sector',
    '世界杯2026': 'themes',
    '磷化铟': 'themes',
    # docs/analysis/26q1/ 内的非季报点评（buffett / 主题 / 跨股）
    'CCL涨价': 'themes',
    '通富微电-AMD26Q1财报联动': 'cross-sector',
    # docs/financial-analysis/ 根的 buffett-风格对比 → cross-sector
    'AMD-Intel-buffett对比': 'cross-sector',
    '立昂微-沪硅产业-buffett对比': 'cross-sector',
    '立讯精密-歌尔股份-buffett对比': 'cross-sector',
}

"""启动时幂等数据种子，供 create_app() 调用"""
from app.seeds.cpu_category import seed_cpu_category
from app.seeds.worldcup_category import seed_worldcup_category
from app.seeds.ascend_category import seed_ascend_category
from app.seeds.copper_category import seed_copper_category
from app.seeds.aerospace_materials_category import seed_aerospace_materials_category
from app.seeds.apple_category import seed_apple_category
from app.seeds.photoresist_category import seed_photoresist_category

__all__ = [
    'seed_cpu_category',
    'seed_worldcup_category',
    'seed_ascend_category',
    'seed_copper_category',
    'seed_aerospace_materials_category',
    'seed_apple_category',
    'seed_photoresist_category',
]

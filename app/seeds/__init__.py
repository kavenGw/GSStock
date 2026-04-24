"""启动时幂等数据种子，供 create_app() 调用"""
from app.seeds.cpu_category import seed_cpu_category

__all__ = ['seed_cpu_category']

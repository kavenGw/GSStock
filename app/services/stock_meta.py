import logging

from app.models.config import Config

logger = logging.getLogger(__name__)


class StockMetaService:
    _cache = None
    _version = None

    @classmethod
    def get_version(cls):
        """获取当前版本号（优先内存缓存）"""
        if cls._version is not None:
            return cls._version
        v = Config.get_value('stock_meta_version', '0')
        cls._version = int(v)
        return cls._version

    @classmethod
    def bump_version(cls):
        """版本号+1，清除内存缓存"""
        v = cls.get_version() + 1
        Config.set_value('stock_meta_version', str(v))
        cls._version = v
        cls._cache = None
        logger.info(f"[StockMeta] version bumped to {v}")

    @classmethod
    def get_meta(cls):
        """返回完整元数据（优先内存缓存）"""
        v = cls.get_version()
        if cls._cache and cls._cache.get('version') == v:
            return cls._cache

        from app.services.stock import StockService
        from app.services.category import CategoryService

        stocks = StockService.get_all_stocks()
        stocks_list = [s.to_dict() for s in stocks]

        category_tree = CategoryService.get_category_tree()
        stock_categories = CategoryService.get_stock_categories_map()

        aliases_raw = StockService.get_all_aliases()
        aliases = {}
        for a in aliases_raw:
            aliases.setdefault(a.stock_code, []).append(a.alias_name)

        meta = {
            'version': v,
            'stocks': stocks_list,
            'category_tree': category_tree,
            'stock_categories': stock_categories,
            'aliases': aliases,
        }
        cls._cache = meta
        return meta

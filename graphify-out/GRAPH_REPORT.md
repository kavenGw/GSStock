# Graph Report - .  (2026-04-22)

## Corpus Check
- 194 files · ~0 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 3334 nodes · 8598 edges · 163 communities detected
- Extraction: 35% EXTRACTED · 65% INFERRED · 0% AMBIGUOUS · INFERRED: 5548 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `E()` - 133 edges
2. `Stock` - 115 edges
3. `MarketIdentifier` - 96 edges
4. `UnifiedStockCache` - 76 edges
5. `T()` - 74 edges
6. `js()` - 71 edges
7. `Y()` - 68 edges
8. `TradingCalendarService` - 67 edges
9. `UnifiedStockDataService` - 67 edges
10. `NotificationService` - 64 edges

## Surprising Connections (you probably didn't know these)
- `获取股票列表（含权重、选中状态、当前持仓）` --uses--> `RebalanceService`  [INFERRED]
  app\routes\rebalance.py → app\services\rebalance.py
- `DailyBriefingStrategy` --uses--> `ValueDipService`  [INFERRED]
  app\strategies\daily_briefing\__init__.py → app\services\value_dip.py
- `盯盘告警服务 — 7种检测器 + 日级去重` --uses--> `Signal`  [INFERRED]
  app\services\watch_alert_service.py → app\strategies\base.py
- `主检测入口          prices: {code: {current_price, change_percent, volume, high, low,` --uses--> `Signal`  [INFERRED]
  app\services\watch_alert_service.py → app\strategies\base.py
- `生成支撑/阻力告警的上下文：下一关键位 + 距离百分比` --uses--> `Signal`  [INFERRED]
  app\services\watch_alert_service.py → app\strategies\base.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (240): a(), aa(), addBox(), addElements(), Ae(), afterDatasetsUpdate(), afterDraw(), afterEvent() (+232 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (534): A(), AA(), Ab(), Ad(), Af(), ag(), Ah(), Ai() (+526 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (65): a(), Ae(), ao, b(), be(), Bt, c(), Ce() (+57 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (155): 从策略目录的 config.yaml 加载配置, Signal, Strategy, 每日简报服务  提供每日简报所需的所有数据聚合，包括： - 关键股票昨日行情（TSLA, GOOG, NVDA, AAPL, WDC, MU, SK海力士, 获取指数数据（按地区分类）          当天永久缓存：首次获取后缓存，同一天内不再重新获取。, 获取期货数据          当天永久缓存：首次获取后缓存，同一天内不再重新获取。, 获取A股行业板块涨幅前5          当天永久缓存：首次获取后缓存，同一天内不再重新获取。, 获取美股行业板块涨幅前5          当天永久缓存：首次获取后缓存，同一天内不再重新获取。 (+147 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (148): Advice, AIAnalyzerService, analyze_batch(), analyze_stock(), _build_prompt(), _call_llm(), _check_ai_enabled(), _collect_stock_data() (+140 more)

### Community 5 - "Community 5"
Cohesion: 0.03
Nodes (46): ABC, fetch_latest(), LLMLayer, LLMProvider, NewsSourceBase, CLSSource, DataSourceFactory, DataSourceProvider (+38 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (57): CompanyNewsService, _extract_urls(), _fetch_all(), fetch_company_news(), _fetch_single_company(), _format_capital_flow(), _format_institution_research(), _format_stock_ranking() (+49 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (5): BriefingPage, _calculate_sector_score(), get_etf_nav(), get_etf_premium_data(), get_sector_ratings()

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (32): BacktestService, _calculate_grade(), 回测验证服务 - 验证威科夫阶段判断和买卖信号的历史准确率, 获取各信号类型的历史胜率，用于前端显示          Returns:             {'信号名': {'win_rate': 0.65,, 从走势数据中提取价格序列，返回 {date_str: close_price}, 评估单条信号（从字典数据）          Args:             signal_data: 包含 signal_date, signal_, 回测买卖信号          1. 获取历史信号记录（SignalCache表）         2. 验证信号触发后5/10/20天的实际走势, get_cached_signals_with_names() (+24 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (36): Config, set_value(), Windows 安全的 RotatingFileHandler，轮转失败时跳过而非崩溃, SafeRotatingFileHandler, detect_gpu(), get_backend_type(), get_ocr_instance(), get_rapidocr_version() (+28 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (28): analyze_batch(), analyze_multi_timeframe(), analyze_single(), _aggregate_group(), aggregate_to_monthly(), aggregate_to_weekly(), AnalysisResult, _ma() (+20 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (20): 安全地创建赛事监控（已在 app context 内）, 早间赛事监控调度（在 app context 内创建全部监控）, 晚间 NBA 监控调度（只清理重建 NBA job，保留 LoL）, 在 app context 内执行策略扫描, 检查是否需要补发每日推送（含周末 extras）, SchedulerEngine, _clear_score(), EsportsMonitorService (+12 more)

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (37): _block_divider(), _block_fields(), _block_header(), _block_section(), build_briefing_blocks(), build_market_blocks(), cleanup_old_flags(), _detect_realtime_changes() (+29 more)

### Community 13 - "Community 13"
Cohesion: 0.05
Nodes (2): check_settlement(), settle_stock()

### Community 14 - "Community 14"
Cohesion: 0.07
Nodes (15): generate_labels(), 数据集构建 — OHLCV 数据转换为训练样本, TrendDataset, _get_model_date(), 推理服务 — 加载训练好的模型生成交易信号, 缓存已加载模型，按 stock_code 推理, 对单只股票生成交易信号          Returns:             {'signal': 'buy/sell/hold', 'confid, TrendPredictor (+7 more)

### Community 15 - "Community 15"
Cohesion: 0.08
Nodes (3): get_ohlc(), _normalize_ohlc(), StockDetailDrawer

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (11): bt, gt(), kt(), mt(), qt(), _t(), vt(), wt() (+3 more)

### Community 17 - "Community 17"
Cohesion: 0.11
Nodes (9): LoadBalancer, 数据源负载均衡器  轮询分配任务到多个数据源，支持熔断后的任务重分配。 支持按市场(A股/美股/港股)进行不同的负载均衡策略。, 轮询分配任务到各数据源          Args:             stock_codes: 股票代码列表             sourc, 重分配失败数据源的任务          Args:             failed_codes: 失败的股票代码列表             f, 使用负载均衡执行数据获取          Args:             stock_codes: 股票代码列表             fetc, 使用优先级模式执行数据获取          主数据源（腾讯/新浪）并行获取，失败的代码再用备用数据源（东方财富），最后yfinance兜底, 按市场进行加权轮询分配          Args:             stock_codes: 股票代码列表             marke, 使用市场特定负载均衡执行数据获取          Args:             stock_codes: 股票代码列表 (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.1
Nodes (11): batch_generate_tags(), create_alias(), create_stock(), delete_alias(), fill_missing_codes(), find_code_by_name(), generate_tags(), get_all_aliases() (+3 more)

### Community 19 - "Community 19"
Cohesion: 0.17
Nodes (1): MemoryCache

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (13): bindEvents(), bindStockEvents(), calculate(), calculate_rebalance(), formatCurrency(), get_stocks(), get_weights(), loadSavedPlans() (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.16
Nodes (1): tn

### Community 22 - "Community 22"
Cohesion: 0.19
Nodes (16): calculate_advice(), _fetch_from_api(), _forward_fill_missing_dates(), get_advice_for_change(), _get_cached_index_prices(), _get_cached_prices(), get_category_trend_data(), get_codes_for_category() (+8 more)

### Community 23 - "Community 23"
Cohesion: 0.16
Nodes (12): _calc_stock_changes(), detect_value_dips(), get_pullback_ranking(), get_sector_performance(), loadPullback(), loadSectors(), 价值洼地分析服务 — 对比板块涨幅，找出洼地, renderCards() (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.27
Nodes (4): 盯盘告警服务 — 7种检测器 + 日级去重, 生成支撑/阻力告警的上下文：下一关键位 + 距离百分比, 主检测入口          prices: {code: {current_price, change_percent, volume, high, low,, WatchAlertService

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (6): generateColors(), highlightTableRows(), loadTransferData(), loadTransferList(), renderAmountDistChart(), renderBuySellChart()

### Community 26 - "Community 26"
Cohesion: 0.12
Nodes (0): 

### Community 27 - "Community 27"
Cohesion: 0.35
Nodes (14): _get_calendar(), get_last_trading_day(), get_market_hours(), get_market_now(), get_next_trading_day(), _get_timezone(), get_trading_days(), is_after_close() (+6 more)

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (13): _analyze(), _cleanup_old_cache(), _dedup(), _enrich_articles(), _fetch_articles(), _fetch_full_content(), _fetch_lives(), _format_slack_message() (+5 more)

### Community 29 - "Community 29"
Cohesion: 0.21
Nodes (7): get_batch_cached_data(), get_cache_with_status(), get_cached_data(), get_complete_cache(), 统一股票数据缓存模型  用于存储所有股票数据的缓存，包括实时价格、OHLC走势数据、指数数据等。 支持智能TTL控制，根据交易时段动态调整缓存有效期。, set_batch_cached_data(), set_cached_data()

### Community 30 - "Community 30"
Cohesion: 0.21
Nodes (4): CircuitBreaker, CircuitState, 平台熔断器  当数据源连续失败时自动熔断，冷却后恢复。, Enum

### Community 31 - "Community 31"
Cohesion: 0.27
Nodes (11): _analyze(), _cleanup_old_cache(), _dedup(), _fetch_article_list(), _fetch_full_content(), _filter_asia(), _format_slack_message(), _load_pushed_hashes() (+3 more)

### Community 32 - "Community 32"
Cohesion: 0.27
Nodes (11): calculate_all(), calculate_bias(), calculate_macd(), calculate_rsi(), calculate_score(), _calculate_support_resistance(), _calculate_trend(), _calculate_volume_indicator() (+3 more)

### Community 33 - "Community 33"
Cohesion: 0.3
Nodes (11): _atr(), _bollinger(), compute_features(), _ema(), _macd(), _moving_average(), _obv(), 特征工程 — OHLCV 数据转换为模型输入特征 (+3 more)

### Community 34 - "Community 34"
Cohesion: 0.17
Nodes (1): analyze()

### Community 35 - "Community 35"
Cohesion: 0.3
Nodes (9): _fetch_batch_yfinance(), _fetch_earnings_akshare(), _fetch_earnings_yfinance(), _format_earnings_result(), get_earnings_dates(), _get_expired_cache(), get_upcoming_earnings(), _save_to_cache() (+1 more)

### Community 36 - "Community 36"
Cohesion: 0.27
Nodes (6): _fetch_from_cme(), _get_fallback_data(), _get_next_meeting(), get_rate_probabilities(), _parse_cme_data(), 美联储利率概率服务  从 CME FedWatch Tool 获取降息/加息概率数据

### Community 37 - "Community 37"
Cohesion: 0.29
Nodes (10): DramPrice, _fetch_and_save(), get_dram_data(), _get_history(), _parse_change(), _parse_price(), DRAM 现货价格服务  爬取 TrendForce DRAM Spot Price 页面，解析 DDR5/DDR4 价格数据。 数据源：https://, 爬取 TrendForce DRAM Spot Price 页面 (+2 more)

### Community 38 - "Community 38"
Cohesion: 0.22
Nodes (4): bindStockNameClick(), bindWeightInputs(), index(), initIndexPage()

### Community 39 - "Community 39"
Cohesion: 0.4
Nodes (9): _attach_quarter_prices(), _date_to_quarter_label(), _fetch_a_share(), _fetch_yfinance(), _get_cache(), get_earnings(), _get_quarter_end_date(), _get_quarter_prices() (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.36
Nodes (9): _do_fetch_espn(), _do_fetch_lol_schedule(), _fetch_espn_scoreboard(), _fetch_lol_esports_schedule(), get_lol_live_scores(), get_lol_schedule(), get_nba_live_scores(), get_nba_schedule() (+1 more)

### Community 41 - "Community 41"
Cohesion: 0.29
Nodes (9): backup_database(), check_migration_needed(), cleanup_legacy_tables(), get_db_paths(), migrate_to_dual_db(), 数据库迁移服务 - 将单一数据库拆分为共享数据库和私有数据库, 检查是否需要执行数据迁移      Returns:         bool: True 如果 stock.db 包含 PRIVATE_TABLES 中, 备份数据库文件      Args:         db_path: 数据库文件路径      Returns:         str: 备份文 (+1 more)

### Community 42 - "Community 42"
Cohesion: 0.42
Nodes (8): check_all_blogs(), _fetch_full_content(), _fetch_html_anthropic(), _fetch_rss(), _get_pushed(), _mark_pushed(), 技术博客监控服务 — 检测新文章并生成中文摘要, _summarize()

### Community 43 - "Community 43"
Cohesion: 0.22
Nodes (1): rs

### Community 44 - "Community 44"
Cohesion: 0.39
Nodes (6): _fetch_releases_from_github(), _filter_new_releases(), get_all_updates(), _get_last_pushed_version(), get_new_releases(), GitHub Release 通用监控服务 - 从 GitHub Releases 获取多仓库版本信息

### Community 45 - "Community 45"
Cohesion: 0.46
Nodes (7): _fetch_html(), fetch_trending(), _get_pushed(), _mark_pushed(), _parse_html(), GitHub Trending 监控服务 — 爬取热门项目并推送新上榜的, _summarize()

### Community 46 - "Community 46"
Cohesion: 0.38
Nodes (6): _default_plugins_dir(), discover_plugin_repos(), _extract_github_repo(), 扫描本地 Claude Code 插件目录，动态发现 marketplace 对应的 GitHub 仓库, 从 known_marketplaces.json 的 source 字段提取 'owner/repo'，非 github 源返回 None, 返回本地已装插件对应的 GitHub 仓库配置，目录缺失/非 github 源自动跳过

### Community 47 - "Community 47"
Cohesion: 0.38
Nodes (4): identify(), is_a_share(), 市场识别工具类  提供统一的股票市场识别和代码转换功能。, to_yfinance()

### Community 48 - "Community 48"
Cohesion: 0.4
Nodes (4): get_available_sources(), get_market_sources(), 数据源配置  配置各市场的数据源优先级、权重和API密钥环境变量。  环境变量配置： - TWELVE_DATA_API_KEY: Twelve Da, 获取指定市场可用的数据源列表（已配置API密钥的）

### Community 49 - "Community 49"
Cohesion: 0.33
Nodes (0): 

### Community 50 - "Community 50"
Cohesion: 0.4
Nodes (2): RateLimiter, 获取一个令牌，不足时阻塞等待。返回 True 表示获取成功。

### Community 51 - "Community 51"
Cohesion: 0.47
Nodes (4): _AkshareProxy, _get_proxy_env(), log_proxy_context(), _proxy_fingerprint()

### Community 52 - "Community 52"
Cohesion: 0.6
Nodes (5): initDailyProfitCharts(), initOverallProfitCharts(), renderCumulativeLine(), renderDailyProfitBar(), renderProfitBarChart()

### Community 53 - "Community 53"
Cohesion: 0.6
Nodes (3): _get_categories_with_position(), get_data(), index()

### Community 54 - "Community 54"
Cohesion: 0.4
Nodes (0): 

### Community 55 - "Community 55"
Cohesion: 0.4
Nodes (1): EventBus

### Community 56 - "Community 56"
Cohesion: 0.5
Nodes (4): calculate_moving_averages(), calculate_support_resistance(), 计算支撑位和压力位      Returns:         {'support': [价格列表, 最多3个], 'resistance': [价格列表, 计算均线信息，返回 ma5/ma10/ma20/ma60/trend

### Community 57 - "Community 57"
Cohesion: 0.5
Nodes (3): build_github_release_update_prompt(), GitHub Release 版本更新摘要 Prompt（通用）, 构建版本更新摘要 prompt      Args:         project_name: 项目显示名称（如 "Claude Code"）

### Community 58 - "Community 58"
Cohesion: 0.5
Nodes (3): build_github_trending_summary_prompt(), GitHub Trending 项目摘要 Prompt, 构建 GitHub Trending 项目摘要 prompt

### Community 59 - "Community 59"
Cohesion: 0.5
Nodes (2): build_batch_tags_prompt(), 批量生成标签的prompt，每个stock含code和name

### Community 60 - "Community 60"
Cohesion: 0.5
Nodes (0): 

### Community 61 - "Community 61"
Cohesion: 0.83
Nodes (3): _get_a_share_market_cap(), _get_foreign_market_cap(), get_market_caps()

### Community 62 - "Community 62"
Cohesion: 0.83
Nodes (3): bump_version(), get_meta(), get_version()

### Community 63 - "Community 63"
Cohesion: 0.67
Nodes (3): get_readonly_status(), is_readonly_mode(), 只读模式工具  只读模式下： - 不从外部服务器获取数据（akshare, yfinance 等） - 不修改 stock.db（共享数据库） - 可

### Community 64 - "Community 64"
Cohesion: 0.67
Nodes (1): 公司识别 prompt：从描述性推送中识别具体公司

### Community 65 - "Community 65"
Cohesion: 0.67
Nodes (2): build_daily_briefing_prompt(), 构建每日简报综合分析 prompt      Args:         all_data: 包含以下 key 的字典，每个 value 为格式化后的文本字符串

### Community 66 - "Community 66"
Cohesion: 0.67
Nodes (0): 

### Community 67 - "Community 67"
Cohesion: 0.67
Nodes (1): 华尔街见闻投行观点整理 Prompt 模板

### Community 68 - "Community 68"
Cohesion: 0.67
Nodes (2): log_operation(), 自动记录操作耗时的上下文管理器      用法:         with log_operation(logger, "数据服务.实时价格") as o

### Community 69 - "Community 69"
Cohesion: 0.67
Nodes (0): 

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): GitHub Release 监控仓库配置

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (0): 

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (0): 

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (0): 

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (0): 

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (0): 

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (1): 获取缓存数据          Args:             stock_code: 股票代码             cache_type: 缓

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (1): 批量获取缓存数据          Args:             stock_codes: 股票代码列表             cache_ty

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (1): 批量设置缓存数据          Args:             data_dict: {stock_code: data} 字典

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (1): 获取最后获取时间          Args:             stock_codes: 股票代码列表             cache_ty

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (1): 清除缓存          Args:             stock_codes: 股票代码列表，为空则清除所有             cach

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (1): 获取已完整的缓存数据          只返回 is_complete=True 的缓存          Args:             sto

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (1): 标记缓存数据为完整          Args:             stock_code: 股票代码             cache_type

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (1): 批量获取数据截止日期          Args:             stock_codes: 股票代码列表             cache_

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (1): 获取缓存数据及其状态          Args:             stock_codes: 股票代码列表             cache_

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (1): feedparser 解析 RSS，返回文章列表

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (1): requests + 正则解析 Anthropic Engineering 页面

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (1): 创建板块，返回 (category, error)

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (1): 更新板块名称，返回 (category, error)

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (1): 更新板块资讯描述，返回 (category, error)

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (1): 获取今日赛程 + 昨日结果          Returns:             {'today': [game, ...], 'yesterday':

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): 获取指定北京日期的 NBA 赛程          Args:             target_date: 目标北京日期          Returns

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): 从 ESPN API 获取指定日期的 NBA 赛程          Returns:             list[dict] 或 None（获取失败）

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): 获取当天所有 NBA 比赛实时比分（查询多天覆盖时区偏移）          Returns:             dict: {match_id: gam

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): 获取所有 LoL 联赛今日赛程 + 昨日结果          Returns:             dict: {league_name: {'today

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): 从 LoL Esports API 获取指定联赛的赛程          API 返回分页数据（无日期过滤参数），需要翻页查找目标日期。         策略：

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): 获取当天所有 LoL 比赛实时比分          Returns:             dict: {match_id: {match_dict + '

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): 获取美联储利率概率          Returns:             {                 'current_rate': 4.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): 获取最近的 FOMC 会议日期          Args:             count: 返回的会议数量          Returns:

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): 获取指定日期范围内的 FOMC 决议          Args:             start_date: 开始日期 (YYYY-MM-DD)

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): 获取指定日期范围内的每日降息概率          Args:             start_date: 开始日期 (YYYY-MM-DD)

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): 将百分比涨跌幅映射到建议类别          逻辑:         - change_pct > 5%: 'buy' (强势上涨)

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): 从 GitHub API 获取最近 10 个 release

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): 筛选出比 last_version 更新的版本；首次运行只取最新 1 个

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): 遍历静态配置 + 本地已装插件对应仓库（按 repo 去重，静态优先），返回每个仓库的更新

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (1): 请求 GitHub Trending 页面

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): 解析 Trending 页面，提取 Top N 项目信息          GitHub Trending 页面结构：         - 每个项目在 <art

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): 主入口：获取新上榜的 trending 项目（含摘要）          Returns:             新项目列表，每项包含 full_name,

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): 获取最新新闻，返回统一格式:         [{             'content': str,             'source_id'

### Community 116 - "Community 116"
Cohesion: 1.0
Nodes (1): 收集所有关注的股票代码（持仓+分类），返回 (codes, name_map)

### Community 117 - "Community 117"
Cohesion: 1.0
Nodes (1): 检测实时分析相对上次推送的变化。返回 (is_first, changes_dict)

### Community 118 - "Community 118"
Cohesion: 1.0
Nodes (1): 格式化所有 GitHub 仓库的版本更新摘要          Returns:             (texts, pushed_versions)

### Community 119 - "Community 119"
Cohesion: 1.0
Nodes (1): 保存权重（upsert），返回 (success, message)

### Community 120 - "Community 120"
Cohesion: 1.0
Nodes (1): 检测所有信号          Args:             ohlc_data: OHLC数据列表，每项包含 {date, open, high,

### Community 121 - "Community 121"
Cohesion: 1.0
Nodes (1): 获取收盘价，兼容 close 和 price 字段

### Community 122 - "Community 122"
Cohesion: 1.0
Nodes (1): 获取最高价，兼容 high 和 close/price 字段

### Community 123 - "Community 123"
Cohesion: 1.0
Nodes (1): 获取开盘价，兼容 open 和 close/price 字段

### Community 124 - "Community 124"
Cohesion: 1.0
Nodes (1): 顶部巨量信号检测（高位放量 + 转弱确认）

### Community 125 - "Community 125"
Cohesion: 1.0
Nodes (1): 创建股票，返回 (stock, error)

### Community 126 - "Community 126"
Cohesion: 1.0
Nodes (1): 更新股票信息，返回 (stock, error)

### Community 127 - "Community 127"
Cohesion: 1.0
Nodes (1): 创建股票别名，返回 (alias, error)

### Community 128 - "Community 128"
Cohesion: 1.0
Nodes (1): 调用 LLM 为单个股票生成标签，返回 (tags_str, error)

### Community 129 - "Community 129"
Cohesion: 1.0
Nodes (1): 手动更新股票标签，返回 (stock, error)

### Community 130 - "Community 130"
Cohesion: 1.0
Nodes (1): 一次性计算所有指标          Args:             ohlcv_data: OHLC数据列表，每项含 {date, open, hi

### Community 131 - "Community 131"
Cohesion: 1.0
Nodes (1): MACD(12,26,9)          Returns:             {dif, dea, histogram, signal: 金叉/

### Community 132 - "Community 132"
Cohesion: 1.0
Nodes (1): RSI多周期计算          Returns:             {rsi_6, rsi_12, rsi_24, status: 超买/超卖/

### Community 133 - "Community 133"
Cohesion: 1.0
Nodes (1): 乖离率计算 (BIAS5, BIAS20)          Returns:             {bias_5, bias_20, warning

### Community 134 - "Community 134"
Cohesion: 1.0
Nodes (1): 综合评分(100分制)          权重: 趋势30% + 乖离20% + MACD15% + 量能15% + RSI10% + 支撑10%

### Community 135 - "Community 135"
Cohesion: 1.0
Nodes (1): 判断是否为交易日          Args:             market: 市场类型 ('A', 'US', 'HK', 'COMEX')

### Community 136 - "Community 136"
Cohesion: 1.0
Nodes (1): 判断是否为周末（使用市场本地时间）          Args:             market: 市场类型             dt: 日期

### Community 137 - "Community 137"
Cohesion: 1.0
Nodes (1): 获取指定日期之前的最后一个交易日          Args:             market: 市场类型             before:

### Community 138 - "Community 138"
Cohesion: 1.0
Nodes (1): 获取指定日期之后的下一个交易日          Args:             market: 市场类型             after: 在

### Community 139 - "Community 139"
Cohesion: 1.0
Nodes (1): 获取市场交易时间（本地时间）          Args:             market: 市场类型             dt: 日期，默认

### Community 140 - "Community 140"
Cohesion: 1.0
Nodes (1): 判断市场当前是否在交易时段          Args:             market: 市场类型             dt: 时间，默认为

### Community 141 - "Community 141"
Cohesion: 1.0
Nodes (1): 判断是否已收盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间

### Community 142 - "Community 142"
Cohesion: 1.0
Nodes (1): 判断是否未开盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间

### Community 143 - "Community 143"
Cohesion: 1.0
Nodes (1): 获取日期范围内的所有交易日          Args:             market: 市场类型             start: 开始日

### Community 144 - "Community 144"
Cohesion: 1.0
Nodes (1): 判断当前是否应该获取数据          综合判断：         - 周末不获取         - 节假日不获取         - 开盘前不

### Community 145 - "Community 145"
Cohesion: 1.0
Nodes (1): 计算价格位置百分位          公式：(当前价 - N日最低) / (N日最高 - N日最低) × 100         - 0 = 处于N日最低

### Community 146 - "Community 146"
Cohesion: 1.0
Nodes (1): 计算均线偏离分          偏离度 = (当前价 - MA20) / MA20 × 100         偏离分 = clamp((偏离度 + 1

### Community 147 - "Community 147"
Cohesion: 1.0
Nodes (1): 计算综合估值评分          综合评分 = 价格位置分 × 0.6 + 均线偏离分 × 0.4          Args:

### Community 148 - "Community 148"
Cohesion: 1.0
Nodes (1): 获取所有板块的 7d/30d/90d 涨幅及个股明细

### Community 149 - "Community 149"
Cohesion: 1.0
Nodes (1): 获取所有股票的高点回退排行（回退幅度从大到小）

### Community 150 - "Community 150"
Cohesion: 1.0
Nodes (1): 验证文件类型和大小，返回 (is_valid, error_message)

### Community 151 - "Community 151"
Cohesion: 1.0
Nodes (1): 验证股票代码格式，支持多市场          Returns: (is_valid, error_message)

### Community 152 - "Community 152"
Cohesion: 1.0
Nodes (0): 

### Community 153 - "Community 153"
Cohesion: 1.0
Nodes (0): 

### Community 154 - "Community 154"
Cohesion: 1.0
Nodes (0): 

### Community 155 - "Community 155"
Cohesion: 1.0
Nodes (0): 

### Community 156 - "Community 156"
Cohesion: 1.0
Nodes (0): 

### Community 157 - "Community 157"
Cohesion: 1.0
Nodes (1): 识别市场类型          Args:             code: 股票代码          Returns:

### Community 158 - "Community 158"
Cohesion: 1.0
Nodes (1): 转换为yfinance格式代码          Args:             code: 原始股票代码          Returns:

### Community 159 - "Community 159"
Cohesion: 1.0
Nodes (1): 判断是否为A股          Args:             code: 股票代码          Returns:

### Community 160 - "Community 160"
Cohesion: 1.0
Nodes (1): 判断是否为指数代码          Args:             code: 股票代码          Returns:

### Community 161 - "Community 161"
Cohesion: 1.0
Nodes (1): 判断是否为ETF代码          Args:             code: 股票代码          Returns:

### Community 162 - "Community 162"
Cohesion: 1.0
Nodes (0): 

## Knowledge Gaps
- **160 isolated node(s):** `数据源配置  配置各市场的数据源优先级、权重和API密钥环境变量。  环境变量配置： - TWELVE_DATA_API_KEY: Twelve Da`, `获取指定市场可用的数据源列表（已配置API密钥的）`, `GitHub Release 监控仓库配置`, `公司识别 prompt：从描述性推送中识别具体公司`, `构建每日简报综合分析 prompt      Args:         all_data: 包含以下 key 的字典，每个 value 为格式化后的文本字符串` (+155 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 70`** (2 nodes): `github_releases.py`, `GitHub Release 监控仓库配置`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (2 nodes): `blog_summary.py`, `build_blog_summary_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (2 nodes): `market_summary.py`, `build_market_summary_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (2 nodes): `news_briefing.py`, `build_summarize_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (2 nodes): `nomura_research.py`, `build_nomura_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (2 nodes): `migrate_news.py`, `migrate()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `blog_monitor.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `esports_config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `github_trending.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `news_config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (1 nodes): `notification_config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (1 nodes): `sector_ratings.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (1 nodes): `stock_codes.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (1 nodes): `获取缓存数据          Args:             stock_code: 股票代码             cache_type: 缓`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `批量获取缓存数据          Args:             stock_codes: 股票代码列表             cache_ty`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (1 nodes): `批量设置缓存数据          Args:             data_dict: {stock_code: data} 字典`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (1 nodes): `获取最后获取时间          Args:             stock_codes: 股票代码列表             cache_ty`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (1 nodes): `清除缓存          Args:             stock_codes: 股票代码列表，为空则清除所有             cach`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `获取已完整的缓存数据          只返回 is_complete=True 的缓存          Args:             sto`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `标记缓存数据为完整          Args:             stock_code: 股票代码             cache_type`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `批量获取数据截止日期          Args:             stock_codes: 股票代码列表             cache_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `获取缓存数据及其状态          Args:             stock_codes: 股票代码列表             cache_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `feedparser 解析 RSS，返回文章列表`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `requests + 正则解析 Anthropic Engineering 页面`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `创建板块，返回 (category, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `更新板块名称，返回 (category, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `更新板块资讯描述，返回 (category, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `获取今日赛程 + 昨日结果          Returns:             {'today': [game, ...], 'yesterday':`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `获取指定北京日期的 NBA 赛程          Args:             target_date: 目标北京日期          Returns`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `从 ESPN API 获取指定日期的 NBA 赛程          Returns:             list[dict] 或 None（获取失败）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `获取当天所有 NBA 比赛实时比分（查询多天覆盖时区偏移）          Returns:             dict: {match_id: gam`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `获取所有 LoL 联赛今日赛程 + 昨日结果          Returns:             dict: {league_name: {'today`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `从 LoL Esports API 获取指定联赛的赛程          API 返回分页数据（无日期过滤参数），需要翻页查找目标日期。         策略：`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `获取当天所有 LoL 比赛实时比分          Returns:             dict: {match_id: {match_dict + '`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `获取美联储利率概率          Returns:             {                 'current_rate': 4.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `获取最近的 FOMC 会议日期          Args:             count: 返回的会议数量          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `获取指定日期范围内的 FOMC 决议          Args:             start_date: 开始日期 (YYYY-MM-DD)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `获取指定日期范围内的每日降息概率          Args:             start_date: 开始日期 (YYYY-MM-DD)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `将百分比涨跌幅映射到建议类别          逻辑:         - change_pct > 5%: 'buy' (强势上涨)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `从 GitHub API 获取最近 10 个 release`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `筛选出比 last_version 更新的版本；首次运行只取最新 1 个`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `遍历静态配置 + 本地已装插件对应仓库（按 repo 去重，静态优先），返回每个仓库的更新`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `请求 GitHub Trending 页面`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `解析 Trending 页面，提取 Top N 项目信息          GitHub Trending 页面结构：         - 每个项目在 <art`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `主入口：获取新上榜的 trending 项目（含摘要）          Returns:             新项目列表，每项包含 full_name,`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `获取最新新闻，返回统一格式:         [{             'content': str,             'source_id'`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 116`** (1 nodes): `收集所有关注的股票代码（持仓+分类），返回 (codes, name_map)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 117`** (1 nodes): `检测实时分析相对上次推送的变化。返回 (is_first, changes_dict)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 118`** (1 nodes): `格式化所有 GitHub 仓库的版本更新摘要          Returns:             (texts, pushed_versions)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 119`** (1 nodes): `保存权重（upsert），返回 (success, message)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 120`** (1 nodes): `检测所有信号          Args:             ohlc_data: OHLC数据列表，每项包含 {date, open, high,`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 121`** (1 nodes): `获取收盘价，兼容 close 和 price 字段`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 122`** (1 nodes): `获取最高价，兼容 high 和 close/price 字段`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 123`** (1 nodes): `获取开盘价，兼容 open 和 close/price 字段`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 124`** (1 nodes): `顶部巨量信号检测（高位放量 + 转弱确认）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 125`** (1 nodes): `创建股票，返回 (stock, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 126`** (1 nodes): `更新股票信息，返回 (stock, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 127`** (1 nodes): `创建股票别名，返回 (alias, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 128`** (1 nodes): `调用 LLM 为单个股票生成标签，返回 (tags_str, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 129`** (1 nodes): `手动更新股票标签，返回 (stock, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 130`** (1 nodes): `一次性计算所有指标          Args:             ohlcv_data: OHLC数据列表，每项含 {date, open, hi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 131`** (1 nodes): `MACD(12,26,9)          Returns:             {dif, dea, histogram, signal: 金叉/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 132`** (1 nodes): `RSI多周期计算          Returns:             {rsi_6, rsi_12, rsi_24, status: 超买/超卖/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 133`** (1 nodes): `乖离率计算 (BIAS5, BIAS20)          Returns:             {bias_5, bias_20, warning`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 134`** (1 nodes): `综合评分(100分制)          权重: 趋势30% + 乖离20% + MACD15% + 量能15% + RSI10% + 支撑10%`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 135`** (1 nodes): `判断是否为交易日          Args:             market: 市场类型 ('A', 'US', 'HK', 'COMEX')`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 136`** (1 nodes): `判断是否为周末（使用市场本地时间）          Args:             market: 市场类型             dt: 日期`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 137`** (1 nodes): `获取指定日期之前的最后一个交易日          Args:             market: 市场类型             before:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 138`** (1 nodes): `获取指定日期之后的下一个交易日          Args:             market: 市场类型             after: 在`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 139`** (1 nodes): `获取市场交易时间（本地时间）          Args:             market: 市场类型             dt: 日期，默认`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 140`** (1 nodes): `判断市场当前是否在交易时段          Args:             market: 市场类型             dt: 时间，默认为`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 141`** (1 nodes): `判断是否已收盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 142`** (1 nodes): `判断是否未开盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 143`** (1 nodes): `获取日期范围内的所有交易日          Args:             market: 市场类型             start: 开始日`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 144`** (1 nodes): `判断当前是否应该获取数据          综合判断：         - 周末不获取         - 节假日不获取         - 开盘前不`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 145`** (1 nodes): `计算价格位置百分位          公式：(当前价 - N日最低) / (N日最高 - N日最低) × 100         - 0 = 处于N日最低`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 146`** (1 nodes): `计算均线偏离分          偏离度 = (当前价 - MA20) / MA20 × 100         偏离分 = clamp((偏离度 + 1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 147`** (1 nodes): `计算综合估值评分          综合评分 = 价格位置分 × 0.6 + 均线偏离分 × 0.4          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 148`** (1 nodes): `获取所有板块的 7d/30d/90d 涨幅及个股明细`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 149`** (1 nodes): `获取所有股票的高点回退排行（回退幅度从大到小）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 150`** (1 nodes): `验证文件类型和大小，返回 (is_valid, error_message)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 151`** (1 nodes): `验证股票代码格式，支持多市场          Returns: (is_valid, error_message)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 152`** (1 nodes): `alert-page.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 153`** (1 nodes): `charts.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 154`** (1 nodes): `index.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 155`** (1 nodes): `relative.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 156`** (1 nodes): `signal-alert.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 157`** (1 nodes): `识别市场类型          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 158`** (1 nodes): `转换为yfinance格式代码          Args:             code: 原始股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 159`** (1 nodes): `判断是否为A股          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 160`** (1 nodes): `判断是否为指数代码          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 161`** (1 nodes): `判断是否为ETF代码          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 162`** (1 nodes): `gunicorn.conf.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NotificationService` connect `Community 4` to `Community 3`, `Community 6`, `Community 9`, `Community 11`, `Community 12`, `Community 28`, `Community 31`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `Stock` connect `Community 3` to `Community 18`, `Community 4`, `Community 6`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `MarketIdentifier` connect `Community 3` to `Community 19`, `Community 4`, `Community 6`, `Community 47`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `E()` (e.g. with `n()` and `T()`) actually correct?**
  _`E()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 113 inferred relationships involving `Stock` (e.g. with `获取分类列表（含持仓股和用户分类，只统计A股）` and `获取指定分类的预警数据（快速路径：只做DB查询+60天OHLC+已缓存信号）`) actually correct?**
  _`Stock` has 113 INFERRED edges - model-reasoned connections that need verification._
- **Are the 95 inferred relationships involving `MarketIdentifier` (e.g. with `获取分类列表（含持仓股和用户分类，只统计A股）` and `获取指定分类的预警数据（快速路径：只做DB查询+60天OHLC+已缓存信号）`) actually correct?**
  _`MarketIdentifier` has 95 INFERRED edges - model-reasoned connections that need verification._
- **Are the 72 inferred relationships involving `UnifiedStockCache` (e.g. with `AIAnalyzerService` and `AI股票分析服务  通过 LLMRouter 路由到智谱 GLM，整合技术面数据为每只股票生成结构化决策建议。 分析结果缓存到 UnifiedStockC`) actually correct?**
  _`UnifiedStockCache` has 72 INFERRED edges - model-reasoned connections that need verification._
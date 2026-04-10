# Graph Report - .  (2026-04-10)

## Corpus Check
- Large corpus: 256 files · ~352,418 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 3567 nodes · 8854 edges · 176 communities detected
- Extraction: 37% EXTRACTED · 63% INFERRED · 0% AMBIGUOUS · INFERRED: 5559 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## God Nodes (most connected - your core abstractions)
1. `E()` - 133 edges
2. `Stock` - 112 edges
3. `MarketIdentifier` - 95 edges
4. `UnifiedStockCache` - 75 edges
5. `T()` - 74 edges
6. `js()` - 71 edges
7. `Y()` - 68 edges
8. `TradingCalendarService` - 66 edges
9. `UnifiedStockDataService` - 66 edges
10. `NotificationService` - 62 edges

## Surprising Connections (you probably didn't know these)
- `缓存验证器  实现8小时缓存有效期验证逻辑，用于控制数据获取频率。` --uses--> `UnifiedStockCache`  [INFERRED]
  app\services\cache_validator.py → app\models\unified_cache.py
- `DailyBriefingStrategy` --uses--> `ValueDipService`  [INFERRED]
  app\strategies\daily_briefing\__init__.py → app\services\value_dip.py
- `盯盘告警服务 — 7种检测器 + 日级去重` --uses--> `Signal`  [INFERRED]
  app\services\watch_alert_service.py → app\strategies\base.py
- `主检测入口          prices: {code: {current_price, change_percent, volume, high, low,` --uses--> `Signal`  [INFERRED]
  app\services\watch_alert_service.py → app\strategies\base.py
- `生成支撑/阻力告警的上下文：下一关键位 + 距离百分比` --uses--> `Signal`  [INFERRED]
  app\services\watch_alert_service.py → app\strategies\base.py

## Hyperedges (group relationships)
- **Three-Layer Cache Pipeline (Memory - DB - API)** — memory_cache, unified_stock_cache, load_balancer, cache_validator, unified_stock_data_service [EXTRACTED 1.00]
- **A-Share Data Source Failover Chain** — tencent_data_source, sina_data_source, eastmoney_data_source, yfinance_data_source, load_balancer, circuit_breaker [EXTRACTED 1.00]
- **Daily Briefing Push Pipeline** — daily_briefing_strategy, notification_service, briefing_service, watch_analysis_service, llm_router, slack_notification [EXTRACTED 1.00]
- **news_ai_tool Channel Push Pipeline** — blog_monitor_service, github_trending_service, github_release_service_doc, notification_service_doc, news_ai_tool_channel [EXTRACTED 0.95]
- **Watch Alert Detection System** — watch_alert_service_doc, watch_alert_strategy_doc, watch_anchor_strategy_doc, watch_analysis_service_doc, td_sequential_service_doc, unified_stock_data_service_doc [EXTRACTED 0.90]
- **GLM Flash Consumer Services** — blog_monitor_service, github_trending_service, github_release_service_doc, nomura_research_service, news_deduplicator_doc, watch_anchor_strategy_doc [INFERRED 0.85]
- **Watch Alert System Evolution** — watch_alert_push_design, watch_intraday_highlow_design, watch_alert_enhance_design, watch_alert_service_spec, seven_alert_detectors, fired_dedup_mechanism [EXTRACTED 0.95]
- **News Deduplication Pipeline** — news_deduplicator_spec, news_dedup_design, news_dedup_llm_design, llm_dedup_4th_channel, suspicious_pair_prefilter, interest_pipeline_spec, company_news_service_spec [EXTRACTED 0.90]
- **Slack Notification Architecture** — slack_channel_routing_design, notification_service_spec, dispatch_signal, channel_routing_rules, event_bus, esports_monitor_service_spec, daily_briefing_strategy_spec [EXTRACTED 0.90]
- **铜业板块持仓** — stock_tongling_youse, stock_beifang_tongye, stock_yunnan_tongye, stock_jiangxi_tongye, stock_tongling_youse_dongwu, stock_beifang_tongye_dongwu [INFERRED 0.90]
- **医药板块持仓** — stock_yifan_yiyao, stock_guangji_yaoye, stock_zhongsheng_yaoye, stock_guangji_yaoye_dongwu [INFERRED 0.90]

## Communities

### Community 0 - "Chart.js Visualization Library"
Cohesion: 0.01
Nodes (251): a(), aa(), addBox(), addElements(), Ae(), afterDatasetsUpdate(), afterDraw(), afterEvent() (+243 more)

### Community 1 - "ECharts Visualization Library"
Cohesion: 0.01
Nodes (534): A(), AA(), Ab(), Ad(), Af(), ag(), Ah(), Ai() (+526 more)

### Community 2 - "AI Analysis & Alert Rationale"
Cohesion: 0.02
Nodes (195): AIAnalyzerService, AI股票分析服务  通过 LLMRouter 路由到智谱 GLM，整合技术面数据为每只股票生成结构化决策建议。 分析结果缓存到 UnifiedStockC, 通过 LLMRouter 调用智谱 GLM, 单只股票AI分析          Args:             stock_code: 股票代码             stock_name:, 批量分析          Args:             stock_list: [{'code': 'xxx', 'name': 'yyy'},, 获取指定分类的预警数据（快速路径：只做DB查询+60天OHLC+已缓存信号）, 获取分类列表（含持仓股和用户分类，只统计A股）, 异步刷新信号缓存：获取365天OHLC并重新计算信号 (+187 more)

### Community 3 - "Bootstrap UI Framework"
Cohesion: 0.01
Nodes (64): a(), Ae(), ao, b(), be(), Bt, c(), Ce() (+56 more)

### Community 4 - "Company News Service"
Cohesion: 0.02
Nodes (103): CompanyNewsService, _extract_urls(), _fetch_all(), fetch_company_news(), _fetch_single_company(), _format_capital_flow(), _format_institution_research(), _format_stock_ranking() (+95 more)

### Community 5 - "Backtesting Engine"
Cohesion: 0.02
Nodes (100): BacktestService, _calculate_grade(), 回测验证服务 - 验证威科夫阶段判断和买卖信号的历史准确率, 获取各信号类型的历史胜率，用于前端显示          Returns:             {'信号名': {'win_rate': 0.65,, 从走势数据中提取价格序列，返回 {date_str: close_price}, 评估单条信号（从字典数据）          Args:             signal_data: 包含 signal_date, signal_, 回测买卖信号          1. 获取历史信号记录（SignalCache表）         2. 验证信号触发后5/10/20天的实际走势, FedRateService (+92 more)

### Community 6 - "Cache & Briefing Infrastructure"
Cohesion: 0.03
Nodes (62): BriefingService, 缓存验证器  实现8小时缓存有效期验证逻辑，用于控制数据获取频率。, CircuitBreaker, CircuitState, 平台熔断器  当数据源连续失败时自动熔断，冷却后恢复。, ClaudeCodeVersionService, DailyBriefingStrategy, Data Sources Configuration (+54 more)

### Community 7 - "LLM & News Source Abstraction"
Cohesion: 0.03
Nodes (47): ABC, fetch_latest(), LLMLayer, LLMProvider, NewsSourceBase, CLSSource, DataSourceFactory, DataSourceProvider (+39 more)

### Community 8 - "App Configuration & Init"
Cohesion: 0.04
Nodes (66): Config, set_value(), _calc_trading_minutes(), check_playwright(), create_app(), DailyBriefingStrategy, _fetch_alert_params(), _format_pullback_message() (+58 more)

### Community 9 - "Blog Monitor & Scheduling"
Cohesion: 0.04
Nodes (78): APScheduler, Blog Monitor Design, Blog Monitor Plan, check_all_blogs(), _fetch_full_content(), _fetch_html_anthropic(), _fetch_rss(), _get_pushed() (+70 more)

### Community 10 - "Briefing Frontend Page"
Cohesion: 0.05
Nodes (5): BriefingPage, _calculate_sector_score(), get_etf_nav(), get_etf_premium_data(), get_sector_ratings()

### Community 11 - "Notification & Slack Push"
Cohesion: 0.1
Nodes (37): _block_divider(), _block_fields(), _block_header(), _block_section(), build_briefing_blocks(), build_market_blocks(), cleanup_old_flags(), _detect_realtime_changes() (+29 more)

### Community 12 - "Trade Management Routes"
Cohesion: 0.05
Nodes (2): check_settlement(), settle_stock()

### Community 13 - "Stock Detail Page"
Cohesion: 0.08
Nodes (3): get_ohlc(), _normalize_ohlc(), StockDetailDrawer

### Community 14 - "Design Specs & Rationale"
Cohesion: 0.06
Nodes (33): Rationale: Graceful Degradation Without AI Params, DailyBriefingStrategy (Spec), Rationale: Dedup Logic Migration to NotificationService, NotificationService.dispatch_signal(), earnings_page Blueprint, EarningsSnapshotStrategy, earnings_snapshot DB Table, Earnings Valuation Page Design (+25 more)

### Community 15 - "Position Planning & Rebalance"
Cohesion: 0.08
Nodes (21): PositionPlan, bindEvents(), bindStockEvents(), calculate(), calculate_rebalance(), get_config(), RebalanceConfig, save_target_value() (+13 more)

### Community 16 - "ML Training Pipeline"
Cohesion: 0.09
Nodes (14): generate_labels(), 数据集构建 — OHLCV 数据转换为训练样本, TrendDataset, _get_model_date(), 推理服务 — 加载训练好的模型生成交易信号, 缓存已加载模型，按 stock_code 推理, 对单只股票生成交易信号          Returns:             {'signal': 'buy/sell/hold', 'confid, TrendPredictor (+6 more)

### Community 17 - "Daily Record"
Cohesion: 0.09
Nodes (18): allowed_file(), api_calc_fee(), api_prev_asset(), calculate_daily_stats(), get_all_trading_dates(), get_daily_profit(), get_daily_profit_history(), get_light_positions() (+10 more)

### Community 18 - "Stock CRUD Management"
Cohesion: 0.1
Nodes (11): batch_generate_tags(), create_alias(), create_stock(), delete_alias(), fill_missing_codes(), find_code_by_name(), generate_tags(), get_all_aliases() (+3 more)

### Community 19 - "Load Balancer & Failover"
Cohesion: 0.12
Nodes (8): LoadBalancer, 轮询分配任务到各数据源          Args:             stock_codes: 股票代码列表             sourc, 重分配失败数据源的任务          Args:             failed_codes: 失败的股票代码列表             f, 使用负载均衡执行数据获取          Args:             stock_codes: 股票代码列表             fetc, 使用优先级模式执行数据获取          主数据源（腾讯/新浪）并行获取，失败的代码再用备用数据源（东方财富），最后yfinance兜底, 按市场进行加权轮询分配          Args:             stock_codes: 股票代码列表             marke, 使用市场特定负载均衡执行数据获取          Args:             stock_codes: 股票代码列表, 数据源负载均衡器（单例）      支持功能：     - 按市场分配不同数据源     - 加权轮询分配     - 自适应权重调整（基于成功率）

### Community 20 - "Position Management"
Cohesion: 0.11
Nodes (7): calculate_daily_change(), get_all_dates(), get_snapshot(), get_stock_history(), get_trend_data(), merge_positions(), save_snapshot()

### Community 21 - "Chart.js Controllers"
Cohesion: 0.17
Nodes (1): tn

### Community 22 - "Value Dip Detection"
Cohesion: 0.16
Nodes (12): _calc_stock_changes(), detect_value_dips(), get_pullback_ranking(), get_sector_performance(), loadPullback(), loadSectors(), 价值洼地分析服务 — 对比板块涨幅，找出洼地, renderCards() (+4 more)

### Community 23 - "Watch Alert Detectors"
Cohesion: 0.27
Nodes (4): 盯盘告警服务 — 7种检测器 + 日级去重, 生成支撑/阻力告警的上下文：下一关键位 + 距离百分比, 主检测入口          prices: {code: {current_price, change_percent, volume, high, low,, WatchAlertService

### Community 24 - "Trade List UI"
Cohesion: 0.14
Nodes (6): generateColors(), highlightTableRows(), loadTransferData(), loadTransferList(), renderAmountDistChart(), renderBuySellChart()

### Community 25 - "Category Management"
Cohesion: 0.12
Nodes (0): 

### Community 26 - "Trading Calendar"
Cohesion: 0.35
Nodes (14): _get_calendar(), get_last_trading_day(), get_market_hours(), get_market_now(), get_next_trading_day(), _get_timezone(), get_trading_days(), is_after_close() (+6 more)

### Community 27 - "Wallstreet News Service"
Cohesion: 0.25
Nodes (13): _analyze(), _cleanup_old_cache(), _dedup(), _enrich_articles(), _fetch_articles(), _fetch_full_content(), _fetch_lives(), _format_slack_message() (+5 more)

### Community 28 - "News Dedup Pipeline (Specs)"
Cohesion: 0.15
Nodes (14): CompanyNewsService (Spec), InterestPipeline (Spec), LLM Flash 4th Dedup Channel, Rationale: Release Lock During LLM Calls, News Dedup Design, Rationale: Greedy Grouping + Longest Content, LLM-Assisted News Dedup Design, news_dedup.py Prompt (+6 more)

### Community 29 - "Portfolio Holdings (Images)"
Cohesion: 0.22
Nodes (14): 中信建投证券 (**1357), 东吴证券 (**6202), 铜业板块, 医药板块, 北方铜业, 北方铜业 (东吴), 广济药业, 广济药业 (东吴) (+6 more)

### Community 30 - "Unified Stock Cache"
Cohesion: 0.21
Nodes (7): get_batch_cached_data(), get_cache_with_status(), get_cached_data(), get_complete_cache(), 统一股票数据缓存模型  用于存储所有股票数据的缓存，包括实时价格、OHLC走势数据、指数数据等。 支持智能TTL控制，根据交易时段动态调整缓存有效期。, set_batch_cached_data(), set_cached_data()

### Community 31 - "Technical Indicators"
Cohesion: 0.27
Nodes (11): calculate_all(), calculate_bias(), calculate_macd(), calculate_rsi(), calculate_score(), _calculate_support_resistance(), _calculate_trend(), _calculate_volume_indicator() (+3 more)

### Community 32 - "ML Feature Engineering"
Cohesion: 0.3
Nodes (11): _atr(), _bollinger(), compute_features(), _ema(), _macd(), _moving_average(), _obv(), 特征工程 — OHLCV 数据转换为模型输入特征 (+3 more)

### Community 33 - "Watch Routes"
Cohesion: 0.17
Nodes (1): analyze()

### Community 34 - "Earnings Data Fetch"
Cohesion: 0.3
Nodes (9): _fetch_batch_yfinance(), _fetch_earnings_akshare(), _fetch_earnings_yfinance(), _format_earnings_result(), get_earnings_dates(), _get_expired_cache(), get_upcoming_earnings(), _save_to_cache() (+1 more)

### Community 35 - "DRAM Price Service"
Cohesion: 0.29
Nodes (10): DramPrice, _fetch_and_save(), get_dram_data(), _get_history(), _parse_change(), _parse_price(), DRAM 现货价格服务  爬取 TrendForce DRAM Spot Price 页面，解析 DDR5/DDR4 价格数据。 数据源：https://, 爬取 TrendForce DRAM Spot Price 页面 (+2 more)

### Community 36 - "Bootstrap Tooltips"
Cohesion: 0.35
Nodes (1): cn

### Community 37 - "AI Stock Analyzer"
Cohesion: 0.36
Nodes (9): analyze_batch(), analyze_stock(), _build_prompt(), _call_llm(), _check_ai_enabled(), _collect_stock_data(), _get_cached(), is_available() (+1 more)

### Community 38 - "Earnings Service"
Cohesion: 0.4
Nodes (9): _attach_quarter_prices(), _date_to_quarter_label(), _fetch_a_share(), _fetch_yfinance(), _get_cache(), get_earnings(), _get_quarter_end_date(), _get_quarter_prices() (+1 more)

### Community 39 - "Market Session & TTL"
Cohesion: 0.44
Nodes (9): filter_by_trading_status(), filter_need_refresh(), get_effective_cache_date(), get_market_for_code(), get_ttl(), group_by_market(), is_cache_valid(), is_data_complete() (+1 more)

### Community 40 - "Database Migration"
Cohesion: 0.29
Nodes (9): backup_database(), check_migration_needed(), cleanup_legacy_tables(), get_db_paths(), migrate_to_dual_db(), 数据库迁移服务 - 将单一数据库拆分为共享数据库和私有数据库, 检查是否需要执行数据迁移      Returns:         bool: True 如果 stock.db 包含 PRIVATE_TABLES 中, 备份数据库文件      Args:         db_path: 数据库文件路径      Returns:         str: 备份文 (+1 more)

### Community 41 - "Alert Page Routes"
Cohesion: 0.31
Nodes (5): get_alert_data(), get_categories(), get_stocks_by_category(), index(), refresh_signals()

### Community 42 - "Watch Service"
Cohesion: 0.22
Nodes (0): 

### Community 43 - "Chart.js Platform"
Cohesion: 0.22
Nodes (1): rs

### Community 44 - "Bank Transfer"
Cohesion: 0.25
Nodes (0): 

### Community 45 - "GitHub Release Monitor"
Cohesion: 0.39
Nodes (6): _fetch_releases_from_github(), _filter_new_releases(), get_all_updates(), _get_last_pushed_version(), get_new_releases(), GitHub Release 通用监控服务 - 从 GitHub Releases 获取多仓库版本信息

### Community 46 - "Data Source Config"
Cohesion: 0.4
Nodes (4): get_available_sources(), get_market_sources(), 数据源配置  配置各市场的数据源优先级、权重和API密钥环境变量。  环境变量配置： - TWELVE_DATA_API_KEY: Twelve Da, 获取指定市场可用的数据源列表（已配置API密钥的）

### Community 47 - "LLM Rate Limiter"
Cohesion: 0.4
Nodes (2): RateLimiter, 获取一个令牌，不足时阻塞等待。返回 True 表示获取成功。

### Community 48 - "Akshare Client Proxy"
Cohesion: 0.47
Nodes (4): _AkshareProxy, _get_proxy_env(), log_proxy_context(), _proxy_fingerprint()

### Community 49 - "Profit Charts UI"
Cohesion: 0.6
Nodes (5): initDailyProfitCharts(), initOverallProfitCharts(), renderCumulativeLine(), renderDailyProfitBar(), renderProfitBarChart()

### Community 50 - "Agents Module"
Cohesion: 0.33
Nodes (6): AGENTS.md Repository Guidelines, System Architecture Document, CLAUDE.md Development Guide, Data Flow & Cache Architecture, GSStock - Personal Stock Management Tool, GSStock Technical Documentation

### Community 51 - "Claude Module"
Cohesion: 0.33
Nodes (6): ClaudeCodeVersionService (Deprecated), Rationale: Config File Over Code, GITHUB_RELEASE_REPOS Config, GitHub Release Monitor Design, github_release_update.py Prompt, GitHubReleaseService (Spec)

### Community 52 - "Channel Module"
Cohesion: 0.33
Nodes (6): Channel Routing Rules, Delete app/notifications/ Directory, EsportsMonitorService (Spec), Slack Bot Token + chat.postMessage API, Slack Multi-Channel Routing Design, Rationale: Webhook to Bot Token Migration

### Community 53 - "Advice Module"
Cohesion: 0.4
Nodes (1): Advice

### Community 54 - "Earnings Module"
Cohesion: 0.6
Nodes (3): _get_categories_with_position(), get_data(), index()

### Community 55 - "Profit Module"
Cohesion: 0.4
Nodes (0): 

### Community 56 - "Valuation Module"
Cohesion: 0.6
Nodes (4): calculate_ma_deviation(), calculate_price_position(), calculate_valuation(), 估值分析服务  计算品种的综合估值评分，包含： - 价格位置分：当前价格在历史区间的百分位 - 均线偏离分：当前价格偏离MA20的程度

### Community 57 - "Support Module"
Cohesion: 0.5
Nodes (4): calculate_moving_averages(), calculate_support_resistance(), 计算支撑位和压力位      Returns:         {'support': [价格列表, 最多3个], 'resistance': [价格列表, 计算均线信息，返回 ma5/ma10/ma20/ma60/trend

### Community 58 - "Debian Module"
Cohesion: 0.5
Nodes (3): Debian systemd Deployment Design, gsstock.service (systemd unit), Rationale: Single Worker + 4 Threads for APScheduler

### Community 59 - "Github Module"
Cohesion: 0.5
Nodes (3): build_github_release_update_prompt(), GitHub Release 版本更新摘要 Prompt（通用）, 构建版本更新摘要 prompt      Args:         project_name: 项目显示名称（如 "Claude Code"）

### Community 60 - "Github Module"
Cohesion: 0.5
Nodes (3): build_github_trending_summary_prompt(), GitHub Trending 项目摘要 Prompt, 构建 GitHub Trending 项目摘要 prompt

### Community 61 - "Stock Module"
Cohesion: 0.5
Nodes (2): build_batch_tags_prompt(), 批量生成标签的prompt，每个stock含code和name

### Community 62 - "Watch Module"
Cohesion: 0.5
Nodes (0): 

### Community 63 - "Readonly Module"
Cohesion: 0.67
Nodes (3): get_readonly_status(), is_readonly_mode(), 只读模式工具  只读模式下： - 不从外部服务器获取数据（akshare, yfinance 等） - 不修改 stock.db（共享数据库） - 可

### Community 64 - "Akshare Module"
Cohesion: 0.5
Nodes (4): akshare Library (A-Share Data), crawl4ai (Web Scraping Library), RapidOCR (ONNX Runtime), Python Dependencies (requirements.txt)

### Community 65 - "Fired Module"
Cohesion: 0.5
Nodes (4): Fired-based Daily Dedup, Rationale: Remove Confirm Delay and Cooldown, Alert Cooldown Mechanism, Rationale: Bypass NM Dedup via Signal.data

### Community 66 - "Run Module"
Cohesion: 0.67
Nodes (0): 

### Community 67 - "Company Module"
Cohesion: 0.67
Nodes (1): 公司识别 prompt：从描述性推送中识别具体公司

### Community 68 - "Daily Module"
Cohesion: 0.67
Nodes (2): build_daily_briefing_prompt(), 构建每日简报综合分析 prompt      Args:         all_data: 包含以下 key 的字典，每个 value 为格式化后的文本字符串

### Community 69 - "News Module"
Cohesion: 0.67
Nodes (0): 

### Community 70 - "Wallstreet Module"
Cohesion: 0.67
Nodes (1): 华尔街见闻投行观点整理 Prompt 模板

### Community 71 - "Log Module"
Cohesion: 0.67
Nodes (2): log_operation(), 自动记录操作耗时的上下文管理器      用法:         with log_operation(logger, "数据服务.实时价格") as o

### Community 72 - "Earnings Module"
Cohesion: 0.67
Nodes (3): EarningsSnapshot Model, Earnings Valuation Page Plan, MarketCapService (Plan)

### Community 73 - "Alert Module"
Cohesion: 0.67
Nodes (3): AI-driven alert_params, watch_analysis.py build_7d_analysis_prompt, WatchAnalysisService (Spec)

### Community 74 - "Github Module"
Cohesion: 1.0
Nodes (1): GitHub Release 监控仓库配置

### Community 75 - "Blog Module"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Market Module"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "News Module"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Nomura Module"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Migrate Module"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Flask Module"
Cohesion: 1.0
Nodes (2): Flask create_app() Factory, _SafeJsonProvider (NaN/Infinity to null)

### Community 81 - "Github Module"
Cohesion: 1.0
Nodes (2): GitHub Release Tracker: openclaw (v2026.4.2), GitHub Release Tracker: superpowers (v5.0.7)

### Community 82 - "Trading Module"
Cohesion: 1.0
Nodes (2): TradingCalendarService (Spec), Volume Time Normalization Formula

### Community 83 - "Blog Module"
Cohesion: 1.0
Nodes (0): 

### Community 84 - "Esports Module"
Cohesion: 1.0
Nodes (0): 

### Community 85 - "Github Module"
Cohesion: 1.0
Nodes (0): 

### Community 86 - "News Module"
Cohesion: 1.0
Nodes (0): 

### Community 87 - "Notification Module"
Cohesion: 1.0
Nodes (0): 

### Community 88 - "Sector Module"
Cohesion: 1.0
Nodes (0): 

### Community 89 - "Stock Module"
Cohesion: 1.0
Nodes (0): 

### Community 90 - "Unified Module"
Cohesion: 1.0
Nodes (1): 获取缓存数据          Args:             stock_code: 股票代码             cache_type: 缓

### Community 91 - "Unified Module"
Cohesion: 1.0
Nodes (1): 批量获取缓存数据          Args:             stock_codes: 股票代码列表             cache_ty

### Community 92 - "Unified Module"
Cohesion: 1.0
Nodes (1): 批量设置缓存数据          Args:             data_dict: {stock_code: data} 字典

### Community 93 - "Unified Module"
Cohesion: 1.0
Nodes (1): 获取最后获取时间          Args:             stock_codes: 股票代码列表             cache_ty

### Community 94 - "Unified Module"
Cohesion: 1.0
Nodes (1): 清除缓存          Args:             stock_codes: 股票代码列表，为空则清除所有             cach

### Community 95 - "Unified Module"
Cohesion: 1.0
Nodes (1): 获取已完整的缓存数据          只返回 is_complete=True 的缓存          Args:             sto

### Community 96 - "Unified Module"
Cohesion: 1.0
Nodes (1): 标记缓存数据为完整          Args:             stock_code: 股票代码             cache_type

### Community 97 - "Unified Module"
Cohesion: 1.0
Nodes (1): 批量获取数据截止日期          Args:             stock_codes: 股票代码列表             cache_

### Community 98 - "Unified Module"
Cohesion: 1.0
Nodes (1): 获取缓存数据及其状态          Args:             stock_codes: 股票代码列表             cache_

### Community 99 - "Blog Module"
Cohesion: 1.0
Nodes (1): feedparser 解析 RSS，返回文章列表

### Community 100 - "Blog Module"
Cohesion: 1.0
Nodes (1): requests + 正则解析 Anthropic Engineering 页面

### Community 101 - "Category Module"
Cohesion: 1.0
Nodes (1): 创建板块，返回 (category, error)

### Community 102 - "Category Module"
Cohesion: 1.0
Nodes (1): 更新板块名称，返回 (category, error)

### Community 103 - "Category Module"
Cohesion: 1.0
Nodes (1): 更新板块资讯描述，返回 (category, error)

### Community 104 - "Esports Module"
Cohesion: 1.0
Nodes (1): 获取今日赛程 + 昨日结果          Returns:             {'today': [game, ...], 'yesterday':

### Community 105 - "Esports Module"
Cohesion: 1.0
Nodes (1): 获取指定北京日期的 NBA 赛程          Args:             target_date: 目标北京日期          Returns

### Community 106 - "Esports Module"
Cohesion: 1.0
Nodes (1): 从 ESPN API 获取指定日期的 NBA 赛程          Returns:             list[dict] 或 None（获取失败）

### Community 107 - "Esports Module"
Cohesion: 1.0
Nodes (1): 获取当天所有 NBA 比赛实时比分（查询多天覆盖时区偏移）          Returns:             dict: {match_id: gam

### Community 108 - "Esports Module"
Cohesion: 1.0
Nodes (1): 获取所有 LoL 联赛今日赛程 + 昨日结果          Returns:             dict: {league_name: {'today

### Community 109 - "Esports Module"
Cohesion: 1.0
Nodes (1): 从 LoL Esports API 获取指定联赛的赛程          API 返回分页数据（无日期过滤参数），需要翻页查找目标日期。         策略：

### Community 110 - "Esports Module"
Cohesion: 1.0
Nodes (1): 获取当天所有 LoL 比赛实时比分          Returns:             dict: {match_id: {match_dict + '

### Community 111 - "Fed Module"
Cohesion: 1.0
Nodes (1): 获取美联储利率概率          Returns:             {                 'current_rate': 4.

### Community 112 - "Fed Module"
Cohesion: 1.0
Nodes (1): 获取最近的 FOMC 会议日期          Args:             count: 返回的会议数量          Returns:

### Community 113 - "Fed Module"
Cohesion: 1.0
Nodes (1): 获取指定日期范围内的 FOMC 决议          Args:             start_date: 开始日期 (YYYY-MM-DD)

### Community 114 - "Fed Module"
Cohesion: 1.0
Nodes (1): 获取指定日期范围内的每日降息概率          Args:             start_date: 开始日期 (YYYY-MM-DD)

### Community 115 - "Futures Module"
Cohesion: 1.0
Nodes (1): 将百分比涨跌幅映射到建议类别          逻辑:         - change_pct > 5%: 'buy' (强势上涨)

### Community 116 - "Github Module"
Cohesion: 1.0
Nodes (1): 从 GitHub API 获取最近 10 个 release

### Community 117 - "Github Module"
Cohesion: 1.0
Nodes (1): 筛选出比 last_version 更新的版本；首次运行只取最新 1 个

### Community 118 - "Github Module"
Cohesion: 1.0
Nodes (1): 请求 GitHub Trending 页面

### Community 119 - "Github Module"
Cohesion: 1.0
Nodes (1): 解析 Trending 页面，提取 Top N 项目信息          GitHub Trending 页面结构：         - 每个项目在 <art

### Community 120 - "Github Module"
Cohesion: 1.0
Nodes (1): 主入口：获取新上榜的 trending 项目（含摘要）          Returns:             新项目列表，每项包含 full_name,

### Community 121 - "Interest Module"
Cohesion: 1.0
Nodes (1): 用 Gemini 识别推送中描述的未具名公司，返回 (结果, 错误原因)

### Community 122 - "Notification Module"
Cohesion: 1.0
Nodes (1): 收集所有关注的股票代码（持仓+分类），返回 (codes, name_map)

### Community 123 - "Notification Module"
Cohesion: 1.0
Nodes (1): 检测实时分析相对上次推送的变化。返回 (is_first, changes_dict)

### Community 124 - "Notification Module"
Cohesion: 1.0
Nodes (1): 格式化所有 GitHub 仓库的版本更新摘要          Returns:             (texts, pushed_versions)

### Community 125 - "Rebalance Module"
Cohesion: 1.0
Nodes (1): 保存权重（upsert），返回 (success, message)

### Community 126 - "Signal Module"
Cohesion: 1.0
Nodes (1): 检测所有信号          Args:             ohlc_data: OHLC数据列表，每项包含 {date, open, high,

### Community 127 - "Signal Module"
Cohesion: 1.0
Nodes (1): 获取收盘价，兼容 close 和 price 字段

### Community 128 - "Signal Module"
Cohesion: 1.0
Nodes (1): 获取最高价，兼容 high 和 close/price 字段

### Community 129 - "Signal Module"
Cohesion: 1.0
Nodes (1): 获取开盘价，兼容 open 和 close/price 字段

### Community 130 - "Signal Module"
Cohesion: 1.0
Nodes (1): 顶部巨量信号检测（高位放量 + 转弱确认）

### Community 131 - "Stock Module"
Cohesion: 1.0
Nodes (1): 创建股票，返回 (stock, error)

### Community 132 - "Stock Module"
Cohesion: 1.0
Nodes (1): 更新股票信息，返回 (stock, error)

### Community 133 - "Stock Module"
Cohesion: 1.0
Nodes (1): 创建股票别名，返回 (alias, error)

### Community 134 - "Stock Module"
Cohesion: 1.0
Nodes (1): 调用 LLM 为单个股票生成标签，返回 (tags_str, error)

### Community 135 - "Stock Module"
Cohesion: 1.0
Nodes (1): 手动更新股票标签，返回 (stock, error)

### Community 136 - "Technical Module"
Cohesion: 1.0
Nodes (1): 一次性计算所有指标          Args:             ohlcv_data: OHLC数据列表，每项含 {date, open, hi

### Community 137 - "Technical Module"
Cohesion: 1.0
Nodes (1): MACD(12,26,9)          Returns:             {dif, dea, histogram, signal: 金叉/

### Community 138 - "Technical Module"
Cohesion: 1.0
Nodes (1): RSI多周期计算          Returns:             {rsi_6, rsi_12, rsi_24, status: 超买/超卖/

### Community 139 - "Technical Module"
Cohesion: 1.0
Nodes (1): 乖离率计算 (BIAS5, BIAS20)          Returns:             {bias_5, bias_20, warning

### Community 140 - "Technical Module"
Cohesion: 1.0
Nodes (1): 综合评分(100分制)          权重: 趋势30% + 乖离20% + MACD15% + 量能15% + RSI10% + 支撑10%

### Community 141 - "Trading Module"
Cohesion: 1.0
Nodes (1): 判断是否为交易日          Args:             market: 市场类型 ('A', 'US', 'HK', 'COMEX')

### Community 142 - "Trading Module"
Cohesion: 1.0
Nodes (1): 判断是否为周末（使用市场本地时间）          Args:             market: 市场类型             dt: 日期

### Community 143 - "Trading Module"
Cohesion: 1.0
Nodes (1): 获取指定日期之前的最后一个交易日          Args:             market: 市场类型             before:

### Community 144 - "Trading Module"
Cohesion: 1.0
Nodes (1): 获取指定日期之后的下一个交易日          Args:             market: 市场类型             after: 在

### Community 145 - "Trading Module"
Cohesion: 1.0
Nodes (1): 获取市场交易时间（本地时间）          Args:             market: 市场类型             dt: 日期，默认

### Community 146 - "Trading Module"
Cohesion: 1.0
Nodes (1): 判断市场当前是否在交易时段          Args:             market: 市场类型             dt: 时间，默认为

### Community 147 - "Trading Module"
Cohesion: 1.0
Nodes (1): 判断是否已收盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间

### Community 148 - "Trading Module"
Cohesion: 1.0
Nodes (1): 判断是否未开盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间

### Community 149 - "Trading Module"
Cohesion: 1.0
Nodes (1): 获取日期范围内的所有交易日          Args:             market: 市场类型             start: 开始日

### Community 150 - "Trading Module"
Cohesion: 1.0
Nodes (1): 判断当前是否应该获取数据          综合判断：         - 周末不获取         - 节假日不获取         - 开盘前不

### Community 151 - "Valuation Module"
Cohesion: 1.0
Nodes (1): 计算价格位置百分位          公式：(当前价 - N日最低) / (N日最高 - N日最低) × 100         - 0 = 处于N日最低

### Community 152 - "Valuation Module"
Cohesion: 1.0
Nodes (1): 计算均线偏离分          偏离度 = (当前价 - MA20) / MA20 × 100         偏离分 = clamp((偏离度 + 1

### Community 153 - "Valuation Module"
Cohesion: 1.0
Nodes (1): 计算综合估值评分          综合评分 = 价格位置分 × 0.6 + 均线偏离分 × 0.4          Args:

### Community 154 - "Value Module"
Cohesion: 1.0
Nodes (1): 获取所有板块的 7d/30d/90d 涨幅及个股明细

### Community 155 - "Value Module"
Cohesion: 1.0
Nodes (1): 获取所有股票的高点回退排行（回退幅度从大到小）

### Community 156 - "Wyckoff Module"
Cohesion: 1.0
Nodes (1): 验证文件类型和大小，返回 (is_valid, error_message)

### Community 157 - "Wyckoff Module"
Cohesion: 1.0
Nodes (1): 验证股票代码格式，支持多市场          Returns: (is_valid, error_message)

### Community 158 - "Base Module"
Cohesion: 1.0
Nodes (1): 获取最新新闻，返回统一格式:         [{             'content': str,             'source_id'

### Community 159 - "Alert Module"
Cohesion: 1.0
Nodes (0): 

### Community 160 - "Charts Module"
Cohesion: 1.0
Nodes (0): 

### Community 161 - "Index Module"
Cohesion: 1.0
Nodes (0): 

### Community 162 - "Relative Module"
Cohesion: 1.0
Nodes (0): 

### Community 163 - "Signal Module"
Cohesion: 1.0
Nodes (0): 

### Community 164 - "Market Module"
Cohesion: 1.0
Nodes (1): 识别市场类型          Args:             code: 股票代码          Returns:

### Community 165 - "Market Module"
Cohesion: 1.0
Nodes (1): 转换为yfinance格式代码          Args:             code: 原始股票代码          Returns:

### Community 166 - "Market Module"
Cohesion: 1.0
Nodes (1): 判断是否为A股          Args:             code: 股票代码          Returns:

### Community 167 - "Market Module"
Cohesion: 1.0
Nodes (1): 判断是否为指数代码          Args:             code: 股票代码          Returns:

### Community 168 - "Market Module"
Cohesion: 1.0
Nodes (1): 判断是否为ETF代码          Args:             code: 股票代码          Returns:

### Community 169 - "Trade Module"
Cohesion: 1.0
Nodes (1): TradeService

### Community 170 - "Daily Module"
Cohesion: 1.0
Nodes (1): DailyRecordService

### Community 171 - "Td Module"
Cohesion: 1.0
Nodes (1): TDSequentialService

### Community 172 - "Volume Module"
Cohesion: 1.0
Nodes (1): VolumeAlertStrategy

### Community 173 - "Pytorch Module"
Cohesion: 1.0
Nodes (1): PyTorch Transformer (AI Signal Prediction)

### Community 174 - "Stock Module"
Cohesion: 1.0
Nodes (1): Stock Manage UI Design

### Community 175 - "Value Module"
Cohesion: 1.0
Nodes (1): value-dip Blueprint

## Knowledge Gaps
- **268 isolated node(s):** `数据源配置  配置各市场的数据源优先级、权重和API密钥环境变量。  环境变量配置： - TWELVE_DATA_API_KEY: Twelve Da`, `获取指定市场可用的数据源列表（已配置API密钥的）`, `GitHub Release 监控仓库配置`, `获取一个令牌，不足时阻塞等待。返回 True 表示获取成功。`, `公司识别 prompt：从描述性推送中识别具体公司` (+263 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Github Module`** (2 nodes): `github_releases.py`, `GitHub Release 监控仓库配置`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Blog Module`** (2 nodes): `blog_summary.py`, `build_blog_summary_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Module`** (2 nodes): `market_summary.py`, `build_market_summary_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `News Module`** (2 nodes): `news_briefing.py`, `build_summarize_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Nomura Module`** (2 nodes): `nomura_research.py`, `build_nomura_prompt()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Migrate Module`** (2 nodes): `migrate_news.py`, `migrate()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Flask Module`** (2 nodes): `Flask create_app() Factory`, `_SafeJsonProvider (NaN/Infinity to null)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (2 nodes): `GitHub Release Tracker: openclaw (v2026.4.2)`, `GitHub Release Tracker: superpowers (v5.0.7)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (2 nodes): `TradingCalendarService (Spec)`, `Volume Time Normalization Formula`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Blog Module`** (1 nodes): `blog_monitor.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `esports_config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (1 nodes): `github_trending.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `News Module`** (1 nodes): `news_config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Notification Module`** (1 nodes): `notification_config.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Sector Module`** (1 nodes): `sector_ratings.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `stock_codes.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `获取缓存数据          Args:             stock_code: 股票代码             cache_type: 缓`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `批量获取缓存数据          Args:             stock_codes: 股票代码列表             cache_ty`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `批量设置缓存数据          Args:             data_dict: {stock_code: data} 字典`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `获取最后获取时间          Args:             stock_codes: 股票代码列表             cache_ty`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `清除缓存          Args:             stock_codes: 股票代码列表，为空则清除所有             cach`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `获取已完整的缓存数据          只返回 is_complete=True 的缓存          Args:             sto`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `标记缓存数据为完整          Args:             stock_code: 股票代码             cache_type`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `批量获取数据截止日期          Args:             stock_codes: 股票代码列表             cache_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Unified Module`** (1 nodes): `获取缓存数据及其状态          Args:             stock_codes: 股票代码列表             cache_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Blog Module`** (1 nodes): `feedparser 解析 RSS，返回文章列表`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Blog Module`** (1 nodes): `requests + 正则解析 Anthropic Engineering 页面`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Category Module`** (1 nodes): `创建板块，返回 (category, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Category Module`** (1 nodes): `更新板块名称，返回 (category, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Category Module`** (1 nodes): `更新板块资讯描述，返回 (category, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `获取今日赛程 + 昨日结果          Returns:             {'today': [game, ...], 'yesterday':`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `获取指定北京日期的 NBA 赛程          Args:             target_date: 目标北京日期          Returns`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `从 ESPN API 获取指定日期的 NBA 赛程          Returns:             list[dict] 或 None（获取失败）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `获取当天所有 NBA 比赛实时比分（查询多天覆盖时区偏移）          Returns:             dict: {match_id: gam`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `获取所有 LoL 联赛今日赛程 + 昨日结果          Returns:             dict: {league_name: {'today`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `从 LoL Esports API 获取指定联赛的赛程          API 返回分页数据（无日期过滤参数），需要翻页查找目标日期。         策略：`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Esports Module`** (1 nodes): `获取当天所有 LoL 比赛实时比分          Returns:             dict: {match_id: {match_dict + '`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Fed Module`** (1 nodes): `获取美联储利率概率          Returns:             {                 'current_rate': 4.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Fed Module`** (1 nodes): `获取最近的 FOMC 会议日期          Args:             count: 返回的会议数量          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Fed Module`** (1 nodes): `获取指定日期范围内的 FOMC 决议          Args:             start_date: 开始日期 (YYYY-MM-DD)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Fed Module`** (1 nodes): `获取指定日期范围内的每日降息概率          Args:             start_date: 开始日期 (YYYY-MM-DD)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Futures Module`** (1 nodes): `将百分比涨跌幅映射到建议类别          逻辑:         - change_pct > 5%: 'buy' (强势上涨)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (1 nodes): `从 GitHub API 获取最近 10 个 release`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (1 nodes): `筛选出比 last_version 更新的版本；首次运行只取最新 1 个`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (1 nodes): `请求 GitHub Trending 页面`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (1 nodes): `解析 Trending 页面，提取 Top N 项目信息          GitHub Trending 页面结构：         - 每个项目在 <art`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Github Module`** (1 nodes): `主入口：获取新上榜的 trending 项目（含摘要）          Returns:             新项目列表，每项包含 full_name,`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Interest Module`** (1 nodes): `用 Gemini 识别推送中描述的未具名公司，返回 (结果, 错误原因)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Notification Module`** (1 nodes): `收集所有关注的股票代码（持仓+分类），返回 (codes, name_map)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Notification Module`** (1 nodes): `检测实时分析相对上次推送的变化。返回 (is_first, changes_dict)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Notification Module`** (1 nodes): `格式化所有 GitHub 仓库的版本更新摘要          Returns:             (texts, pushed_versions)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Rebalance Module`** (1 nodes): `保存权重（upsert），返回 (success, message)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Signal Module`** (1 nodes): `检测所有信号          Args:             ohlc_data: OHLC数据列表，每项包含 {date, open, high,`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Signal Module`** (1 nodes): `获取收盘价，兼容 close 和 price 字段`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Signal Module`** (1 nodes): `获取最高价，兼容 high 和 close/price 字段`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Signal Module`** (1 nodes): `获取开盘价，兼容 open 和 close/price 字段`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Signal Module`** (1 nodes): `顶部巨量信号检测（高位放量 + 转弱确认）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `创建股票，返回 (stock, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `更新股票信息，返回 (stock, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `创建股票别名，返回 (alias, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `调用 LLM 为单个股票生成标签，返回 (tags_str, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `手动更新股票标签，返回 (stock, error)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Technical Module`** (1 nodes): `一次性计算所有指标          Args:             ohlcv_data: OHLC数据列表，每项含 {date, open, hi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Technical Module`** (1 nodes): `MACD(12,26,9)          Returns:             {dif, dea, histogram, signal: 金叉/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Technical Module`** (1 nodes): `RSI多周期计算          Returns:             {rsi_6, rsi_12, rsi_24, status: 超买/超卖/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Technical Module`** (1 nodes): `乖离率计算 (BIAS5, BIAS20)          Returns:             {bias_5, bias_20, warning`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Technical Module`** (1 nodes): `综合评分(100分制)          权重: 趋势30% + 乖离20% + MACD15% + 量能15% + RSI10% + 支撑10%`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `判断是否为交易日          Args:             market: 市场类型 ('A', 'US', 'HK', 'COMEX')`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `判断是否为周末（使用市场本地时间）          Args:             market: 市场类型             dt: 日期`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `获取指定日期之前的最后一个交易日          Args:             market: 市场类型             before:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `获取指定日期之后的下一个交易日          Args:             market: 市场类型             after: 在`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `获取市场交易时间（本地时间）          Args:             market: 市场类型             dt: 日期，默认`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `判断市场当前是否在交易时段          Args:             market: 市场类型             dt: 时间，默认为`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `判断是否已收盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `判断是否未开盘          Args:             market: 市场类型             dt: 时间，默认为市场当前时间`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `获取日期范围内的所有交易日          Args:             market: 市场类型             start: 开始日`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trading Module`** (1 nodes): `判断当前是否应该获取数据          综合判断：         - 周末不获取         - 节假日不获取         - 开盘前不`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Valuation Module`** (1 nodes): `计算价格位置百分位          公式：(当前价 - N日最低) / (N日最高 - N日最低) × 100         - 0 = 处于N日最低`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Valuation Module`** (1 nodes): `计算均线偏离分          偏离度 = (当前价 - MA20) / MA20 × 100         偏离分 = clamp((偏离度 + 1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Valuation Module`** (1 nodes): `计算综合估值评分          综合评分 = 价格位置分 × 0.6 + 均线偏离分 × 0.4          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Value Module`** (1 nodes): `获取所有板块的 7d/30d/90d 涨幅及个股明细`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Value Module`** (1 nodes): `获取所有股票的高点回退排行（回退幅度从大到小）`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Wyckoff Module`** (1 nodes): `验证文件类型和大小，返回 (is_valid, error_message)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Wyckoff Module`** (1 nodes): `验证股票代码格式，支持多市场          Returns: (is_valid, error_message)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Module`** (1 nodes): `获取最新新闻，返回统一格式:         [{             'content': str,             'source_id'`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Alert Module`** (1 nodes): `alert-page.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Charts Module`** (1 nodes): `charts.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Index Module`** (1 nodes): `index.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Relative Module`** (1 nodes): `relative.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Signal Module`** (1 nodes): `signal-alert.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Module`** (1 nodes): `识别市场类型          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Module`** (1 nodes): `转换为yfinance格式代码          Args:             code: 原始股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Module`** (1 nodes): `判断是否为A股          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Module`** (1 nodes): `判断是否为指数代码          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Market Module`** (1 nodes): `判断是否为ETF代码          Args:             code: 股票代码          Returns:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Trade Module`** (1 nodes): `TradeService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Daily Module`** (1 nodes): `DailyRecordService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Td Module`** (1 nodes): `TDSequentialService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Volume Module`** (1 nodes): `VolumeAlertStrategy`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Pytorch Module`** (1 nodes): `PyTorch Transformer (AI Signal Prediction)`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Stock Module`** (1 nodes): `Stock Manage UI Design`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Value Module`** (1 nodes): `value-dip Blueprint`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NotificationService` connect `Company News Service` to `AI Analysis & Alert Rationale`, `App Configuration & Init`, `Blog Monitor & Scheduling`, `Notification & Slack Push`, `Wallstreet News Service`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `Stock` connect `AI Analysis & Alert Rationale` to `Stock CRUD Management`, `Company News Service`, `Backtesting Engine`, `Position Planning & Rebalance`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `MarketIdentifier` connect `AI Analysis & Alert Rationale` to `App Configuration & Init`, `Company News Service`, `Cache & Briefing Infrastructure`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 132 inferred relationships involving `E()` (e.g. with `n()` and `T()`) actually correct?**
  _`E()` has 132 INFERRED edges - model-reasoned connections that need verification._
- **Are the 110 inferred relationships involving `Stock` (e.g. with `获取分类列表（含持仓股和用户分类，只统计A股）` and `获取指定分类的预警数据（快速路径：只做DB查询+60天OHLC+已缓存信号）`) actually correct?**
  _`Stock` has 110 INFERRED edges - model-reasoned connections that need verification._
- **Are the 94 inferred relationships involving `MarketIdentifier` (e.g. with `获取分类列表（含持仓股和用户分类，只统计A股）` and `获取指定分类的预警数据（快速路径：只做DB查询+60天OHLC+已缓存信号）`) actually correct?**
  _`MarketIdentifier` has 94 INFERRED edges - model-reasoned connections that need verification._
- **Are the 71 inferred relationships involving `UnifiedStockCache` (e.g. with `AIAnalyzerService` and `AI股票分析服务  通过 LLMRouter 路由到智谱 GLM，整合技术面数据为每只股票生成结构化决策建议。 分析结果缓存到 UnifiedStockC`) actually correct?**
  _`UnifiedStockCache` has 71 INFERRED edges - model-reasoned connections that need verification._
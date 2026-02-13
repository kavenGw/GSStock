"""AI股票分析服务

接入OpenAI兼容API，整合技术面数据为每只股票生成结构化决策建议。
分析结果缓存到 UnifiedStockCache（cache_type='ai_analysis'），每日有效。

配置通过环境变量：
- AI_API_KEY: API密钥（必需）
- AI_BASE_URL: API地址（默认 https://api.openai.com/v1）
- AI_MODEL: 模型名称（默认 gpt-4o-mini）
"""
import json
import logging
import os
from datetime import date

logger = logging.getLogger(__name__)

# AI配置 - 直接从环境变量读取
AI_API_KEY = os.environ.get('AI_API_KEY', '')
AI_BASE_URL = os.environ.get('AI_BASE_URL', 'https://api.openai.com/v1')
AI_MODEL = os.environ.get('AI_MODEL', 'gpt-4o-mini')
AI_ENABLED = bool(AI_API_KEY)


class AIAnalyzerService:
    """AI股票分析服务"""

    @staticmethod
    def is_available() -> bool:
        return AI_ENABLED

    @staticmethod
    def analyze_stock(stock_code: str, stock_name: str = '', force: bool = False) -> dict:
        """单只股票AI分析

        Args:
            stock_code: 股票代码
            stock_name: 股票名称（可选，用于prompt）
            force: 是否强制刷新（忽略缓存）

        Returns:
            AI分析结果字典
        """
        if not AI_ENABLED:
            return {'error': 'AI分析未配置，请在 .env 中设置 AI_API_KEY'}

        # 检查缓存
        if not force:
            cached = AIAnalyzerService._get_cached(stock_code)
            if cached:
                cached['from_cache'] = True
                return cached

        # 收集数据
        stock_data = AIAnalyzerService._collect_stock_data(stock_code, stock_name)
        if not stock_data:
            return {'error': f'无法获取 {stock_code} 的数据'}

        # 构建prompt并调用API
        prompt = AIAnalyzerService._build_prompt(stock_data)
        result = AIAnalyzerService._call_llm(prompt)

        if 'error' in result:
            return result

        # 缓存结果
        result['stock_code'] = stock_code
        result['stock_name'] = stock_data.get('name', stock_name)
        result['from_cache'] = False
        AIAnalyzerService._save_cache(stock_code, result)

        return result

    @staticmethod
    def analyze_batch(stock_list: list) -> list:
        """批量分析

        Args:
            stock_list: [{'code': 'xxx', 'name': 'yyy'}, ...]

        Returns:
            分析结果列表
        """
        results = []
        for stock in stock_list:
            code = stock.get('code', '')
            name = stock.get('name', '')
            try:
                result = AIAnalyzerService.analyze_stock(code, name)
                results.append(result)
            except Exception as e:
                logger.error(f"AI分析 {code} 失败: {e}")
                results.append({
                    'stock_code': code,
                    'stock_name': name,
                    'error': str(e)
                })
        return results

    @staticmethod
    def _collect_stock_data(stock_code: str, stock_name: str = '') -> dict:
        """收集股票的各维度数据"""
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.technical_indicators import TechnicalIndicatorService
        from app.models.wyckoff import WyckoffAutoResult

        data = {'code': stock_code, 'name': stock_name}

        try:
            # 实时价格
            price_result = unified_stock_data_service.get_realtime_prices([stock_code])
            prices = price_result.get('prices', [])
            if prices:
                p = prices[0]
                data['price'] = p.get('price', 0)
                data['change_pct'] = p.get('change_pct', 0)
                data['volume'] = p.get('volume', 0)
                if not stock_name:
                    data['name'] = p.get('name', stock_code)
                data['market'] = p.get('market', '')

            # OHLCV走势（60天，用于技术指标）
            trend_result = unified_stock_data_service.get_trend_data([stock_code], days=60)
            stocks_data = trend_result.get('stocks', [])
            ohlcv = []
            if stocks_data:
                ohlcv_raw = stocks_data[0].get('data', [])
                if ohlcv_raw:
                    ohlcv = [d.to_dict() if hasattr(d, 'to_dict') else d for d in ohlcv_raw]

            # 技术指标
            if ohlcv and len(ohlcv) >= 26:
                indicators = TechnicalIndicatorService.calculate_all(ohlcv)
                if indicators:
                    data['indicators'] = {
                        'score': indicators['score'],
                        'signal': indicators['signal'],
                        'signal_text': indicators['signal_text'],
                        'macd': indicators['macd']['signal'],
                        'rsi_6': indicators['rsi'].get('rsi_6', 0),
                        'rsi_status': indicators['rsi']['status'],
                        'bias_20': indicators['bias']['bias_20'],
                        'bias_warning': indicators['bias'].get('warning_text', ''),
                        'trend_state': indicators['trend']['state'],
                        'ma5': indicators['trend'].get('ma5', 0),
                        'ma20': indicators['trend'].get('ma20', 0),
                        'ma60': indicators['trend'].get('ma60', 0),
                        'volume_state': indicators['volume']['state'],
                        'support': indicators['support'].get('support', 0),
                        'resistance': indicators['support'].get('resistance', 0),
                    }

                # 最近5天行情
                if len(ohlcv) >= 5:
                    recent = ohlcv[-5:]
                    data['recent_5d'] = [{
                        'date': d.get('date', ''),
                        'close': d.get('close', 0),
                        'change_pct': d.get('change_pct', 0),
                        'volume': d.get('volume', 0),
                    } for d in recent]

            # 威科夫分析（最近一次）
            try:
                wyckoff = WyckoffAutoResult.query.filter_by(
                    stock_code=stock_code, status='success'
                ).order_by(WyckoffAutoResult.analysis_date.desc()).first()
                if wyckoff:
                    data['wyckoff'] = {
                        'phase': wyckoff.phase,
                        'advice': wyckoff.advice,
                        'support': wyckoff.support_price,
                        'resistance': wyckoff.resistance_price,
                        'date': wyckoff.analysis_date.isoformat() if wyckoff.analysis_date else '',
                    }
            except Exception:
                pass

            # 持仓信息
            try:
                from app.models.position import Position
                from app.services.position import PositionService
                latest_date = PositionService.get_latest_date()
                if latest_date:
                    pos = Position.query.filter_by(
                        date=latest_date, stock_code=stock_code
                    ).first()
                    if pos:
                        cost = pos.cost_price
                        current = data.get('price', pos.current_price)
                        profit_pct = ((current - cost) / cost * 100) if cost > 0 else 0
                        data['position'] = {
                            'quantity': pos.quantity,
                            'cost_price': round(cost, 2),
                            'profit_pct': round(profit_pct, 2),
                        }
            except Exception:
                pass

        except Exception as e:
            logger.error(f"收集 {stock_code} 数据失败: {e}", exc_info=True)

        return data if data.get('price') or data.get('indicators') else None

    @staticmethod
    def _build_prompt(stock_data: dict) -> str:
        """构建分析prompt"""
        code = stock_data.get('code', '')
        name = stock_data.get('name', code)
        price = stock_data.get('price', 0)
        change_pct = stock_data.get('change_pct', 0)
        market = stock_data.get('market', '')

        sections = [f"# {name}({code}) 技术分析"]

        # 今日行情
        sections.append(f"\n## 今日行情\n- 当前价: {price}\n- 涨跌幅: {change_pct}%")

        # 技术指标
        ind = stock_data.get('indicators', {})
        if ind:
            sections.append(f"""
## 技术指标
- 综合评分: {ind.get('score', 0)}/100 ({ind.get('signal_text', '')})
- 均线排列: {ind.get('trend_state', '')} (MA5:{ind.get('ma5', 0)} MA20:{ind.get('ma20', 0)} MA60:{ind.get('ma60', 0)})
- MACD信号: {ind.get('macd', '')}
- RSI(6): {ind.get('rsi_6', 0)} ({ind.get('rsi_status', '')})
- 乖离率(MA20): {ind.get('bias_20', 0)}% {ind.get('bias_warning', '')}
- 量能状态: {ind.get('volume_state', '')}
- 支撑位: {ind.get('support', 0)} | 阻力位: {ind.get('resistance', 0)}""")

        # 威科夫
        wyckoff = stock_data.get('wyckoff', {})
        if wyckoff:
            phase_map = {
                'accumulation': '吸筹', 'markup': '上涨',
                'distribution': '派发', 'markdown': '下跌'
            }
            advice_map = {
                'buy': '买入', 'hold': '持有', 'sell': '卖出', 'watch': '观望'
            }
            sections.append(f"""
## 威科夫分析 ({wyckoff.get('date', '')})
- 阶段: {phase_map.get(wyckoff.get('phase', ''), wyckoff.get('phase', ''))}
- 建议: {advice_map.get(wyckoff.get('advice', ''), wyckoff.get('advice', ''))}
- 支撑: {wyckoff.get('support', '')} | 阻力: {wyckoff.get('resistance', '')}""")

        # 持仓
        pos = stock_data.get('position', {})
        if pos:
            sections.append(f"""
## 持仓信息
- 持仓数量: {pos.get('quantity', 0)}
- 成本价: {pos.get('cost_price', 0)}
- 浮盈: {pos.get('profit_pct', 0)}%""")

        # 最近5日走势
        recent = stock_data.get('recent_5d', [])
        if recent:
            lines = [f"- {d['date']}: {d['close']} ({d['change_pct']}%)" for d in recent]
            sections.append(f"\n## 近5日走势\n" + "\n".join(lines))

        data_text = "\n".join(sections)

        return f"""你是一位专业的股票技术分析师。请基于以下数据给出结构化分析。

{data_text}

## 分析要求
1. 综合以上所有指标，给出明确的操作建议
2. 核心纪律：乖离率>5%不追高，多头排列是做多前提
3. 必须给出精确的买入价/止损价/目标价
4. 给出仓位建议（重仓/中仓/轻仓/空仓）

请严格按以下JSON格式返回，不要添加其他文字：

{{
  "conclusion": "一句话结论（20字以内）",
  "signal": "STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL",
  "score": 75,
  "confidence": "high/medium/low",
  "analysis": {{
    "trend": "趋势分析（50字以内）",
    "volume": "量能分析（30字以内）",
    "risk": "风险因素（30字以内）"
  }},
  "action_plan": {{
    "buy_price": 0,
    "stop_loss": 0,
    "target_price": 0,
    "position_advice": "轻仓试探/中仓持有/重仓加码/空仓观望"
  }}
}}"""

    @staticmethod
    def _call_llm(prompt: str) -> dict:
        """调用LLM API"""
        import httpx

        try:
            response = httpx.post(
                f"{AI_BASE_URL.rstrip('/')}/chat/completions",
                headers={
                    'Authorization': f'Bearer {AI_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': AI_MODEL,
                    'messages': [
                        {'role': 'system', 'content': '你是专业的股票技术分析师，只输出JSON格式结果。'},
                        {'role': 'user', 'content': prompt},
                    ],
                    'temperature': 0.3,
                    'max_tokens': 500,
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            content = data['choices'][0]['message']['content'].strip()
            # 提取JSON（可能被```包裹）
            if '```' in content:
                start = content.find('{')
                end = content.rfind('}') + 1
                content = content[start:end]

            return json.loads(content)

        except httpx.TimeoutException:
            return {'error': 'AI分析超时，请稍后重试'}
        except httpx.HTTPStatusError as e:
            logger.error(f"AI API 错误: {e.response.status_code} {e.response.text}")
            return {'error': f'AI API 错误: {e.response.status_code}'}
        except json.JSONDecodeError:
            logger.error(f"AI返回非JSON格式: {content[:200] if 'content' in dir() else 'N/A'}")
            return {'error': 'AI返回格式错误'}
        except Exception as e:
            logger.error(f"AI分析失败: {e}", exc_info=True)
            return {'error': f'AI分析失败: {str(e)}'}

    @staticmethod
    def _get_cached(stock_code: str) -> dict | None:
        """获取缓存的分析结果"""
        from app.models.unified_cache import UnifiedStockCache
        data = UnifiedStockCache.get_cached_data(stock_code, 'ai_analysis', date.today())
        return data if data and isinstance(data, dict) and 'error' not in data else None

    @staticmethod
    def _save_cache(stock_code: str, result: dict):
        """缓存分析结果"""
        from app.models.unified_cache import UnifiedStockCache
        try:
            # 不缓存 from_cache 标记
            cache_data = {k: v for k, v in result.items() if k != 'from_cache'}
            UnifiedStockCache.set_cached_data(
                stock_code, 'ai_analysis', cache_data,
                date.today(), is_complete=True
            )
        except Exception as e:
            logger.warning(f"缓存AI分析结果失败: {e}")

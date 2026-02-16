import os
import re
import logging
import uuid
import tempfile
from datetime import datetime
from PIL import Image
from config import Config

logger = logging.getLogger(__name__)


def get_rapidocr_version() -> str:
    """获取 rapidocr-onnxruntime 版本"""
    try:
        import importlib.metadata
        return importlib.metadata.version('rapidocr-onnxruntime')
    except Exception:
        return 'unknown'


class OcrResultParser:
    """处理不同版本 RapidOCR 的输出格式兼容性

    旧版本 (1.3.x 及更早): 返回 (result, elapsed_time)
        result 格式: [[bbox, text, confidence], ...]

    新版本 (1.4.x+): 返回 (result, elapsed_time) 或 RapidOCRResult 对象
        result 格式可能是:
        - [[bbox, text, confidence], ...]  (旧格式)
        - [{'box': [...], 'txt': '...', 'score': ...}, ...]  (新格式)
    """

    @staticmethod
    def parse(ocr_output) -> list:
        """解析 OCR 输出，返回统一格式 [[bbox, text, confidence], ...]

        Args:
            ocr_output: OCR 函数的原始返回值

        Returns:
            统一格式的结果列表: [[bbox, text, confidence], ...]
            如果无结果返回空列表
        """
        # 处理元组返回值 (result, elapsed_time)
        if isinstance(ocr_output, tuple):
            result = ocr_output[0]
        else:
            result = ocr_output

        # 处理 RapidOCRResult 对象（新版本可能返回）
        if hasattr(result, '__iter__') and hasattr(result, '__len__'):
            # 可迭代对象，继续处理
            pass
        elif result is None:
            return []
        else:
            # 尝试获取结果属性
            if hasattr(result, 'result'):
                result = result.result
            elif hasattr(result, 'data'):
                result = result.data
            else:
                logger.warning(f"[OCR] 未知的 OCR 结果类型: {type(result)}")
                return []

        if not result:
            return []

        # 统一转换为 [[bbox, text, confidence], ...] 格式
        normalized = []
        for item in result:
            try:
                parsed = OcrResultParser._parse_item(item)
                if parsed:
                    normalized.append(parsed)
            except Exception as e:
                logger.warning(f"[OCR] 解析 OCR 结果项失败: {e}, item={item}")
                continue

        return normalized

    @staticmethod
    def _parse_item(item) -> list:
        """解析单个结果项

        支持格式:
        1. [bbox, text, confidence] - 旧格式列表
        2. {'box': bbox, 'txt': text, 'score': confidence} - 新格式字典
        3. 其他可能的变体
        """
        # 格式1: 列表 [bbox, text, confidence]
        if isinstance(item, (list, tuple)):
            if len(item) >= 2:
                bbox = item[0]
                text = item[1]
                confidence = item[2] if len(item) > 2 else 0.0
                return [bbox, str(text), float(confidence) if confidence else 0.0]

        # 格式2: 字典 {'box': ..., 'txt': ..., 'score': ...}
        elif isinstance(item, dict):
            bbox = item.get('box') or item.get('bbox') or item.get('position') or []
            text = item.get('txt') or item.get('text') or item.get('content') or ''
            confidence = item.get('score') or item.get('confidence') or item.get('conf') or 0.0
            if text:
                return [bbox, str(text), float(confidence) if confidence else 0.0]

        return None


class ImagePreprocessor:
    """图片预处理，控制输入尺寸"""

    @staticmethod
    def preprocess(image_path: str) -> str:
        """预处理图片，返回处理后的路径

        - 若图片尺寸超过 MAX_SIZE，使用 LANCZOS 算法缩放
        - 创建临时文件存储处理后的图片
        - 调用方负责清理临时文件
        """
        max_size = Config.OCR_MAX_SIZE

        with Image.open(image_path) as img:
            width, height = img.size

            if width <= max_size and height <= max_size:
                return image_path

            # 计算缩放比例
            scale = min(max_size / width, max_size / height)
            new_width = int(width * scale)
            new_height = int(height * scale)

            logger.debug(f"[OCR] 图片缩放: {width}x{height} -> {new_width}x{new_height}")

            resized = img.resize((new_width, new_height), Image.LANCZOS)

            # 创建临时文件
            suffix = os.path.splitext(image_path)[1] or '.png'
            fd, temp_path = tempfile.mkstemp(suffix=suffix)
            os.close(fd)

            resized.save(temp_path)
            return temp_path


class OcrBackend:
    """管理 OCR 后端初始化和 GPU 检测"""

    _instance = None
    _backend_type = None

    @classmethod
    def detect_gpu(cls) -> str:
        """检测可用的 GPU 加速方式

        返回: 'cuda', 'directml', 'cpu'
        """
        if not Config.OCR_USE_GPU:
            return 'cpu'

        backend = Config.OCR_GPU_BACKEND
        if backend != 'auto':
            return backend

        # 检测 CUDA
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if 'CUDAExecutionProvider' in providers:
                return 'cuda'
            if 'DmlExecutionProvider' in providers:
                return 'directml'
        except Exception as e:
            logger.warning(f"[OCR] GPU 检测失败: {e}")

        return 'cpu'

    @classmethod
    def get_ocr_instance(cls):
        """获取配置好的 RapidOCR 实例（单例）"""
        if cls._instance is not None:
            return cls._instance

        from rapidocr_onnxruntime import RapidOCR

        backend = cls.detect_gpu()
        cls._backend_type = backend

        # 记录版本信息
        version = get_rapidocr_version()
        logger.info(f"[OCR] OCR 后端: {backend.upper()}, rapidocr-onnxruntime 版本: {version}")

        # 根据后端配置 providers
        if backend == 'cuda':
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
        elif backend == 'directml':
            providers = ['DmlExecutionProvider', 'CPUExecutionProvider']
        else:
            providers = ['CPUExecutionProvider']

        cls._instance = RapidOCR()
        return cls._instance

    @classmethod
    def get_backend_type(cls) -> str:
        """获取当前后端类型"""
        if cls._backend_type is None:
            cls.get_ocr_instance()
        return cls._backend_type


class OcrLogger:
    """管理单次OCR操作的日志记录"""

    def __init__(self, image_path: str):
        self.image_path = image_path
        self.timestamp = datetime.now()
        self.file = None

        log_dir = os.path.join(Config.LOG_DIR, 'ocr')
        os.makedirs(log_dir, exist_ok=True)

        filename = f"ocr_{self.timestamp.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}.log"
        self.log_path = os.path.join(log_dir, filename)
        self.file = open(self.log_path, 'w', encoding='utf-8')

        self._write_header()

    def _write_header(self):
        self.file.write("=" * 80 + "\n")
        self.file.write("OCR识别日志\n")
        self.file.write("=" * 80 + "\n")
        self.file.write(f"时间: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n")
        self.file.write(f"图片: {self.image_path}\n\n")
        self.file.flush()

    def log_raw_result(self, result):
        """记录 RapidOCR 原始结果

        RapidOCR 格式: [[bbox, text, confidence], ...]
        """
        self.file.write("=" * 80 + "\n")
        self.file.write("原始OCR结果\n")
        self.file.write("=" * 80 + "\n")

        if not result:
            self.file.write("无识别结果\n\n")
            self.file.flush()
            return

        for idx, line in enumerate(result, 1):
            box = line[0]
            text = line[1]
            confidence = line[2] if len(line) > 2 else 0.0

            self.file.write(f"[{idx}] 位置: {box}\n")
            self.file.write(f"    文本: \"{text}\"\n")
            self.file.write(f"    置信度: {confidence:.2f}\n\n")
        self.file.flush()

    def log_sorted_lines(self, lines: list[dict]):
        """记录排序后的文本行"""
        self.file.write("=" * 80 + "\n")
        self.file.write("排序后文本行\n")
        self.file.write("=" * 80 + "\n")

        if not lines:
            self.file.write("无文本行\n\n")
            self.file.flush()
            return

        for idx, line in enumerate(lines, 1):
            self.file.write(f"行{idx} (y={line['y']:.0f}): {line['text']} [置信度: {line['confidence']:.2f}]\n")
        self.file.write("\n")
        self.file.flush()

    def log_parse_attempt(self, line_num: int, text: str, status: str, data: dict = None):
        """记录单行解析尝试"""
        if data:
            # 交易记录格式
            if 'trade_type' in data:
                trade_type_str = '买入' if data['trade_type'] == 'buy' else '卖出'
                self.file.write(f"行{line_num}: 匹配成功 - {trade_type_str} "
                              f"代码:{data.get('stock_code', '')}, "
                              f"名称:{data.get('stock_name', '')}, "
                              f"数量:{data.get('quantity', '')}, "
                              f"价格:{data.get('price', '')}\n")
            # 持仓记录格式
            else:
                self.file.write(f"行{line_num}: 匹配成功 - 代码:{data.get('stock_code', '')}, "
                              f"名称:{data.get('stock_name', '')}, "
                              f"数量:{data.get('quantity', '')}, "
                              f"总金额:{data.get('total_amount', '')}, "
                              f"现价:{data.get('current_price', '')}\n")
        else:
            self.file.write(f"行{line_num}: 跳过 - {status}\n")

    def begin_parse_section(self):
        """开始解析过程记录"""
        self.file.write("=" * 80 + "\n")
        self.file.write("解析过程\n")
        self.file.write("=" * 80 + "\n")

    def log_final_result(self, results: list[dict]):
        """记录最终解析结果"""
        self.file.write("\n" + "=" * 80 + "\n")
        self.file.write(f"最终结果 (共{len(results)}条)\n")
        self.file.write("=" * 80 + "\n")

        if not results:
            self.file.write("无识别记录\n")
            self.file.flush()
            return

        for idx, r in enumerate(results, 1):
            # 交易记录格式
            if 'trade_type' in r:
                trade_type_str = '买入' if r['trade_type'] == 'buy' else '卖出'
                self.file.write(f"{idx}. {trade_type_str} | {r['stock_code']} | {r['stock_name']} | "
                              f"{r['quantity']}股 | 价格:{r.get('price', '')}\n")
            # 持仓记录格式
            else:
                self.file.write(f"{idx}. {r['stock_code']} | {r['stock_name']} | "
                              f"{r['quantity']}股 | 总金额:{r.get('total_amount', '')} | 现价:{r.get('current_price', '')}\n")
        self.file.flush()

    def log_error(self, error: Exception):
        """记录错误信息"""
        import traceback
        self.file.write("\n" + "=" * 80 + "\n")
        self.file.write("错误信息\n")
        self.file.write("=" * 80 + "\n")
        self.file.write(f"异常类型: {type(error).__name__}\n")
        self.file.write(f"异常信息: {error}\n")
        self.file.write(f"堆栈跟踪:\n{traceback.format_exc()}\n")
        self.file.flush()

    def close(self):
        """关闭日志文件"""
        if self.file:
            self.file.close()
            self.file = None

def preload_model():
    """应用启动时预加载 OCR 模型"""
    logger.info("[OCR] 预加载 OCR 模型...")
    try:
        OcrBackend.get_ocr_instance()
        backend = OcrBackend.get_backend_type()
        logger.info(f"[OCR] OCR 模型加载完成，后端: {backend.upper()}")
    except Exception as e:
        logger.warning(f"[OCR] OCR 模型预加载失败: {e}")


class OcrService:
    @staticmethod
    def recognize(image_path: str) -> dict:
        """识别持仓截图，返回股票数据和账户概览

        返回格式: {
            'positions': [...],  # 股票持仓列表
            'account': {         # 账户概览（可能为空）
                'total_asset': float,      # 总资产
                'daily_profit': float,     # 当日盈亏
                'daily_profit_pct': float  # 当日盈亏百分比
            }
        }
        """
        logger.info(f"[OCR] 开始OCR识别: {image_path}")

        ocr_logger = None
        temp_path = None

        try:
            ocr_logger = OcrLogger(image_path)
        except Exception as e:
            logger.warning(f"[OCR] 创建OCR日志失败: {e}")

        try:
            # 预处理图片
            temp_path = ImagePreprocessor.preprocess(image_path)
            process_path = temp_path

            # 获取 OCR 实例并识别
            ocr = OcrBackend.get_ocr_instance()
            ocr_output = ocr(process_path)

            # 使用兼容性解析器处理不同版本的输出格式
            result = OcrResultParser.parse(ocr_output)

            if ocr_logger:
                ocr_logger.log_raw_result(result)

            if not result:
                logger.info("[OCR] 识别完成，未识别到数据")
                if ocr_logger:
                    ocr_logger.log_final_result([])
                    ocr_logger.close()
                return {'positions': [], 'account': {}}

            # RapidOCR 格式: [[bbox, text, confidence], ...]
            lines = []
            for line in result:
                box = line[0]
                text = line[1]
                confidence = line[2] if len(line) > 2 else 0.0
                # 计算中心坐标（bbox 格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]）
                x_center = (box[0][0] + box[2][0]) / 2
                y_center = (box[0][1] + box[2][1]) / 2
                lines.append({'x': x_center, 'y': y_center, 'text': text, 'confidence': confidence})

            lines.sort(key=lambda x: x['y'])

            # 合并 Y 坐标相近的文本块为逻辑行
            lines = OcrService._merge_lines_by_y(lines)

            if ocr_logger:
                ocr_logger.log_sorted_lines(lines)

            # 解析账户概览数据（总资产、当日盈亏）
            account_data = OcrService._parse_account_overview(lines)

            # 解析持仓数据
            positions = OcrService._parse_lines(lines, ocr_logger)

            if ocr_logger:
                ocr_logger.log_final_result(positions)
                ocr_logger.close()

            logger.info(f"[OCR] 识别完成，识别到{len(positions)}条记录，账户数据: {account_data}")
            return {'positions': positions, 'account': account_data}

        except Exception as e:
            logger.error(f"[OCR] 识别异常: {e}", exc_info=True)
            if ocr_logger:
                ocr_logger.log_error(e)
                ocr_logger.close()
            raise
        finally:
            # 清理临时文件
            if temp_path and temp_path != image_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def _parse_account_overview(lines: list[dict]) -> dict:
        """解析账户概览信息（总资产、当日参考盈亏）

        从截图顶部区域识别：
        - 总资产: 240,472.25
        - 当日参考盈亏: +11,634.06 5.08%

        注意：标签和数值通常在不同行，数值在标签下方
        """
        account = {}

        for i, line in enumerate(lines):
            text = line['text']

            # 匹配总资产（标签行，数值通常在下一行）
            if '总资产' in text and 'total_asset' not in account:
                # 优先查找下一行的数字（数值通常在标签下方）
                if i + 1 < len(lines):
                    next_text = lines[i + 1]['text']
                    # 排除包含其他标签的行
                    if '盈亏' not in next_text and '市值' not in next_text:
                        numbers = re.findall(r'[\d,]+\.?\d*', next_text)
                        if numbers:
                            try:
                                val = float(numbers[0].replace(',', ''))
                                if val > 1000:  # 总资产通常大于1000
                                    account['total_asset'] = val
                            except ValueError:
                                pass

                # 如果下一行没找到，尝试从当前行提取
                if 'total_asset' not in account:
                    numbers = re.findall(r'[\d,]+\.?\d*', text)
                    if numbers:
                        try:
                            val = float(numbers[0].replace(',', ''))
                            if val > 1000:
                                account['total_asset'] = val
                        except ValueError:
                            pass

            # 匹配当日参考盈亏（标签行，数值通常在下一行）
            if '当日' in text and ('盈亏' in text or '参考' in text) and 'daily_profit' not in account:
                # 优先查找下一行的数字和百分比
                if i + 1 < len(lines):
                    next_text = lines[i + 1]['text']
                    # 匹配带正负号的数字（盈亏值）
                    profit_match = re.search(r'([+-])?([\d,]+\.?\d*)', next_text)
                    pct_match = re.search(r'([\d.]+)%', next_text)

                    if profit_match:
                        try:
                            sign = profit_match.group(1) or ''
                            val = float(profit_match.group(2).replace(',', ''))
                            if sign == '-':
                                val = -val
                            account['daily_profit'] = val
                        except ValueError:
                            pass
                    if pct_match:
                        try:
                            account['daily_profit_pct'] = float(pct_match.group(1))
                        except ValueError:
                            pass

                # 如果下一行没找到，尝试从当前行提取
                if 'daily_profit' not in account:
                    profit_match = re.search(r'([+-])?([\d,]+\.?\d*)', text)
                    pct_match = re.search(r'([\d.]+)%', text)
                    if profit_match:
                        try:
                            sign = profit_match.group(1) or ''
                            val = float(profit_match.group(2).replace(',', ''))
                            if sign == '-':
                                val = -val
                            # 排除太大的数字（可能是总资产）
                            if val < 100000:
                                account['daily_profit'] = val
                        except ValueError:
                            pass
                    if pct_match:
                        try:
                            account['daily_profit_pct'] = float(pct_match.group(1))
                        except ValueError:
                            pass

        return account

    @staticmethod
    def _merge_lines_by_y(lines: list[dict], threshold: float = 20) -> list[dict]:
        """将 Y 坐标相近的文本块合并为逻辑行

        Args:
            lines: 按 Y 坐标排序后的文本块列表
            threshold: Y 坐标差值阈值，小于此值视为同一行
        """
        if not lines:
            return []

        merged = []
        current_group = [lines[0]]

        for line in lines[1:]:
            if abs(line['y'] - current_group[0]['y']) <= threshold:
                current_group.append(line)
            else:
                # 按 X 坐标排序后合并文本
                current_group.sort(key=lambda x: x.get('x', 0))
                merged.append({
                    'y': current_group[0]['y'],
                    'text': ' '.join(item['text'] for item in current_group),
                    'confidence': min(item['confidence'] for item in current_group)
                })
                current_group = [line]

        # 处理最后一组
        if current_group:
            current_group.sort(key=lambda x: x.get('x', 0))
            merged.append({
                'y': current_group[0]['y'],
                'text': ' '.join(item['text'] for item in current_group),
                'confidence': min(item['confidence'] for item in current_group)
            })

        return merged

    @staticmethod
    def _parse_lines(lines: list[dict], ocr_logger: OcrLogger = None) -> list[dict]:
        """解析OCR识别的文本行，提取股票数据"""
        results = []
        i = 0

        if ocr_logger:
            ocr_logger.begin_parse_section()

        while i < len(lines):
            text = lines[i]['text']
            line_num = i + 1

            # 匹配股票代码（6位数字）
            code_match = re.search(r'\b(\d{6})\b', text)
            if code_match:
                stock_code = code_match.group(1)
                numbers = re.findall(r'[\d,]+\.?\d*', text)
                numbers = [float(n.replace(',', '')) for n in numbers if n and n != stock_code]
                name_match = re.search(r'[\u4e00-\u9fa5A-Za-z]+', text)
                stock_name = name_match.group(0) if name_match else ''

                if len(numbers) >= 3:
                    quantity = int(numbers[0])
                    cost_price = numbers[1]
                    data = {
                        'stock_code': stock_code,
                        'stock_name': stock_name,
                        'quantity': quantity,
                        'total_amount': cost_price * quantity,
                        'current_price': numbers[2],
                    }
                    results.append(data)
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, None, data)
                else:
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, f"数字不足(需要3个，实际{len(numbers)}个)")
                i += 1
                continue

            # 匹配股票名称开头（必须以中文或字母开头，后续可含数字）
            name_match = re.match(r'^([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9]*(?:ETF)?)', text)
            if name_match:
                stock_name = name_match.group(1)
                # 从名称后面提取数字（排除名称中的数字）
                name_end_pos = name_match.end()
                remaining_text = text[name_end_pos:]
                numbers1 = re.findall(r'-?[\d,]+\.?\d*', remaining_text)
                numbers1 = [n.replace(',', '') for n in numbers1 if n]
                numbers1 = [float(n) for n in numbers1 if n]

                # 查找下一行的数字（现价在第二行最后）
                numbers2 = []
                if i + 1 < len(lines):
                    next_text = lines[i + 1]['text']
                    # 跳过纯中文行
                    if not re.match(r'^[\u4e00-\u9fa5]+$', next_text):
                        numbers2 = re.findall(r'-?[\d,]+\.?\d*', next_text)
                        numbers2 = [float(n.replace(',', '')) for n in numbers2 if n]

                # 第一行格式：名称 盈亏 持仓 成本
                if len(numbers1) >= 3:
                    current_price = numbers2[-1] if numbers2 else numbers1[-1]
                    quantity = int(numbers1[1])
                    cost_price = numbers1[2]
                    data = {
                        'stock_code': '',
                        'stock_name': stock_name,
                        'quantity': quantity,
                        'total_amount': cost_price * quantity,
                        'current_price': current_price,
                    }
                    results.append(data)
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, None, data)
                    i += 2 if numbers2 else 1
                    continue
                else:
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, f"名称匹配但数字不足(需要3个，实际{len(numbers1)}个)")

            if ocr_logger and not code_match and not name_match:
                ocr_logger.log_parse_attempt(line_num, text, "无股票代码或名称匹配")

            i += 1

        return results

    @staticmethod
    def recognize_trade(image_path: str) -> list[dict]:
        """识别交易截图，返回交易数据列表"""
        logger.info(f"[OCR.交易] 开始识别交易截图: {image_path}")

        ocr_logger = None
        temp_path = None

        try:
            ocr_logger = OcrLogger(image_path)
        except Exception as e:
            logger.warning(f"[OCR.交易] 创建OCR日志失败: {e}")

        try:
            # 预处理图片
            temp_path = ImagePreprocessor.preprocess(image_path)
            process_path = temp_path

            # 获取 OCR 实例并识别
            ocr = OcrBackend.get_ocr_instance()
            ocr_output = ocr(process_path)

            # 使用兼容性解析器处理不同版本的输出格式
            result = OcrResultParser.parse(ocr_output)

            if ocr_logger:
                ocr_logger.log_raw_result(result)

            if not result:
                logger.info("[OCR.交易] 识别完成，未识别到交易数据")
                if ocr_logger:
                    ocr_logger.log_final_result([])
                    ocr_logger.close()
                return []

            # RapidOCR 格式: [[bbox, text, confidence], ...]
            lines = []
            for line in result:
                box = line[0]
                text = line[1]
                confidence = line[2] if len(line) > 2 else 0.0
                x_center = (box[0][0] + box[2][0]) / 2
                y_center = (box[0][1] + box[2][1]) / 2
                lines.append({'x': x_center, 'y': y_center, 'text': text, 'confidence': confidence})

            lines.sort(key=lambda x: x['y'])

            # 合并 Y 坐标相近的文本块为逻辑行
            lines = OcrService._merge_lines_by_y(lines)

            if ocr_logger:
                ocr_logger.log_sorted_lines(lines)

            results = OcrService._parse_trade_lines(lines, ocr_logger)

            if ocr_logger:
                ocr_logger.log_final_result(results)
                ocr_logger.close()

            logger.info(f"[OCR.交易] 识别完成，识别到{len(results)}条记录")
            return results

        except Exception as e:
            logger.error(f"[OCR.交易] 识别异常: {e}", exc_info=True)
            if ocr_logger:
                ocr_logger.log_error(e)
                ocr_logger.close()
            raise
        finally:
            # 清理临时文件
            if temp_path and temp_path != image_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @staticmethod
    def _parse_trade_lines(lines: list[dict], ocr_logger: OcrLogger = None) -> list[dict]:
        """解析交易截图文本行

        支持格式：
        1. "买云南铜业 18.470 900 16623.000" (买/卖+名称+均价+数量+金额)
        2. "买入 000878 云南铜业 900 18.470" (传统格式)
        3. "德明利 买入" + 下一行 "241.990 100" (中信建投格式，名称和买卖分开，数据在下一行)
        """
        results = []
        i = 0

        if ocr_logger:
            ocr_logger.begin_parse_section()

        while i < len(lines):
            text = lines[i]['text']
            line_num = i + 1

            # 格式3：中信建投格式 - "名称 买入/卖出"，数据在下一行
            # 匹配：名称 + 空格 + 买入/卖出（名称在前）
            name_trade_match = re.match(r'^([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9]*(?:ETF)?)\s+(买入|卖出)$', text)
            if name_trade_match and i + 1 < len(lines):
                stock_name = name_trade_match.group(1)
                trade_type = 'buy' if name_trade_match.group(2) == '买入' else 'sell'

                # 从下一行提取数字（成交价、成交量）
                next_text = lines[i + 1]['text']
                numbers = re.findall(r'[\d,]+\.?\d*', next_text)
                numbers = [float(n.replace(',', '')) for n in numbers if n]

                if len(numbers) >= 2:
                    price = numbers[0]
                    quantity = int(numbers[1])
                    data = {
                        'stock_code': '',
                        'stock_name': stock_name,
                        'trade_type': trade_type,
                        'quantity': quantity,
                        'price': price,
                    }
                    results.append(data)
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, None, data)
                    i += 2
                    continue
                else:
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, f"下一行数字不足(需要2个，实际{len(numbers)}个)")

            # 格式1：检测交易类型和股票名称（格式：买云南铜业 或 卖亿帆医药）
            trade_name_match = re.match(r'^(买|卖)([\u4e00-\u9fa5A-Za-z][\u4e00-\u9fa5A-Za-z0-9]*(?:ETF)?)', text)
            if trade_name_match:
                trade_type = 'buy' if trade_name_match.group(1) == '买' else 'sell'
                stock_name = trade_name_match.group(2)

                # 从名称后面提取数字：均价、数量、金额
                name_end_pos = trade_name_match.end()
                remaining_text = text[name_end_pos:]
                numbers = re.findall(r'[\d,]+\.?\d*', remaining_text)
                numbers = [float(n.replace(',', '')) for n in numbers if n]

                if len(numbers) >= 2:
                    price = numbers[0]
                    quantity = int(numbers[1])
                    data = {
                        'stock_code': '',
                        'stock_name': stock_name,
                        'trade_type': trade_type,
                        'quantity': quantity,
                        'price': price,
                    }
                    results.append(data)
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, None, data)
                    i += 1
                    continue
                else:
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, f"数字不足(需要2个，实际{len(numbers)}个)")

            # 格式2：传统格式 - 检测 买入/卖出 + 股票代码
            trade_type = None
            if '买入' in text:
                trade_type = 'buy'
            elif '卖出' in text:
                trade_type = 'sell'

            code_match = re.search(r'\b(\d{6})\b', text)

            if code_match and trade_type:
                stock_code = code_match.group(1)
                numbers = re.findall(r'[\d,]+\.?\d*', text)
                numbers = [n.replace(',', '') for n in numbers if n and n != stock_code]
                numbers = [float(n) for n in numbers]

                if len(numbers) >= 2:
                    data = {
                        'stock_code': stock_code,
                        'stock_name': '',
                        'trade_type': trade_type,
                        'quantity': int(numbers[0]),
                        'price': numbers[1],
                    }
                    name_match = re.search(r'[\u4e00-\u9fa5A-Za-z]+', text)
                    if name_match:
                        name = name_match.group(0)
                        if name not in ['买入', '卖出']:
                            data['stock_name'] = name
                    results.append(data)
                    if ocr_logger:
                        ocr_logger.log_parse_attempt(line_num, text, None, data)
                    i += 1
                    continue

            if ocr_logger:
                ocr_logger.log_parse_attempt(line_num, text, "未匹配交易模式")

            i += 1

        return results

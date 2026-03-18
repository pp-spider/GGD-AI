import cv2
import numpy as np
import os
import re
import threading
import time
from typing import List, Dict, Optional

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
template_path = os.path.join(BASE_DIR, 'template_imgs')

# 全局配置：默认使用模板匹配，可选 'template' 或 'ocr'
RECOGNITION_MODE = 'ocr'

# 加载所有模板（全局缓存）
_templates = None

# 全局 OCR 识别器（延迟加载）
_ocr_pipeline = None
_ocr_lock = threading.Lock()
_is_loading = False


def set_recognition_mode(mode: str):
    """
    设置识别模式

    Args:
        mode: 'template' 使用模板匹配, 'ocr' 使用 PaddleOCR-VL
    """
    global RECOGNITION_MODE
    if mode in ['template', 'ocr']:
        RECOGNITION_MODE = mode
        print(f"[识别模式] 已切换为: {mode}")
    else:
        raise ValueError("mode 必须是 'template' 或 'ocr'")


def get_recognition_mode() -> str:
    """获取当前识别模式"""
    return RECOGNITION_MODE


def _load_templates():
    """加载所有数字模板"""
    global _templates
    if _templates is None:
        _templates = {}
        template_files = ['01', '02', '06', '10', '11', '12', '13']
        for digit in template_files:
            template_file = f'{template_path}/{digit}.png'
            if os.path.exists(template_file):
                _templates[digit] = cv2.imread(template_file, 0)
            else:
                print(f"警告: 模板文件不存在 {template_file}")
    return _templates


def _load_ocr_model():
    """延迟加载 PaddleOCR-VL 模型"""
    global _ocr_pipeline, _is_loading

    if _ocr_pipeline is not None:
        return _ocr_pipeline

    with _ocr_lock:
        if _ocr_pipeline is None and not _is_loading:
            _is_loading = True
            try:
                from paddleocr import PaddleOCRVL
                print("[PaddleOCRVL] 正在加载模型...")
                _ocr_pipeline = PaddleOCRVL(
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_layout_detection=False,
                    device='cpu'
                )
                print("[PaddleOCRVL] 模型加载完成")
            except Exception as e:
                print(f"[PaddleOCRVL] 模型加载失败: {e}")
                raise
            finally:
                _is_loading = False

    return _ocr_pipeline


def _extract_text_from_result(result) -> List[Dict]:
    """从 PaddleOCR 结果中提取文本信息"""
    texts = []

    # 从 parsing_res_list 中提取文本
    if result.get('parsing_res_list'):
        for item in result['parsing_res_list']:
            if getattr(item, 'content', ''):
                texts.append({
                    'text': getattr(item, 'content', ''),
                    'bbox': getattr(item, 'bbox', None),
                })
    return texts


def _recognize_image_ocr(img_array: np.ndarray) -> List[Dict]:
    """
    使用 PaddleOCR-VL 识别图像

    Args:
        img_array: 灰度图像数组

    Returns:
        List[Dict]: 识别结果列表
    """
    pipeline = _load_ocr_model()
    if pipeline is None:
        return []

    try:
        # OCR 需要 BGR 格式，将灰度转为 BGR
        if len(img_array.shape) == 2:
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)
        else:
            img_bgr = img_array

        start = time.time()
        output = pipeline.predict(img_bgr)
        end = time.time()
        print(f"[OCR] 识别耗时：{end-start:.3f}s")

        all_texts = []
        for res in output:
            texts = _extract_text_from_result(res)
            all_texts.extend(texts)

        return all_texts
    except Exception as e:
        print(f"[OCR] 识别失败: {e}")
        return []

def _recognize_image_template(card_top: np.ndarray) -> Optional[str]:
    """
    使用模板匹配识别图像

    Args:
        card_top: 卡片顶部区域图像（灰度）

    Returns:
        str: 识别到的数字，未识别返回 None
    """
    templates = _load_templates()
    if not templates:
        print("错误: 没有加载到任何模板")
        return None

    best_digit = None
    best_score = 0.0
    threshold = 0.8

    for digit, template in templates.items():
        if template is None:
            continue
        # 模板匹配
        res = cv2.matchTemplate(card_top, template, cv2.TM_CCOEFF_NORMED)
        # 获取最大匹配分数
        _, max_val, _, _ = cv2.minMaxLoc(res)

        # 记录全局最大
        if max_val > best_score:
            best_score = max_val
            best_digit = digit

    # 只有全局最大分数超过阈值才返回
    if best_score >= threshold and best_digit is not None:
        return best_digit
    return None


def extract_player_num_from_array(img, save_debug=False, debug_prefix=""):
    """
    从图像数组中提取玩家数字

    Args:
        img: 图像 (numpy array, BGR 或灰度)
        save_debug: 是否保存调试图片
        debug_prefix: 调试图片文件名前缀

    Returns:
        str: 识别到的数字 (如 '02', '06')，未识别返回 None
    """
    if img is None or img.size == 0:
        return None

    # 确保是灰度图
    if len(img.shape) == 3:
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        img_gray = img.copy()

    # OTSU二值化
    _, binary_otsu = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    t_h, t_w = img_gray.shape
    total_square = t_w * t_h

    # 找白色连通域（卡片）
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary_otsu)

    for i in range(1, num_labels):
        x, y, w, h, area = stats[i]
        square = w * h
        white_ratio = area / square if square > 0 else 0

        # 卡片占整张图的大概0.01-0.02，白色占比卡片的0.7以上，卡片长宽比2-3
        if total_square * 0.01 < square < total_square * 0.02 and white_ratio > 0.7 and 2.0 < w / h < 3.0:
            # 保存调试图片
            if save_debug:
                temp_dir = os.path.join(BASE_DIR, 'temp_images')
                os.makedirs(temp_dir, exist_ok=True)
                cv2.imwrite(os.path.join(temp_dir, f'{debug_prefix}_card_{i}.png'), binary_otsu[y:y + h, x:x + w])
                cv2.imwrite(os.path.join(temp_dir, f'{debug_prefix}_card_{i}_.png'),
                           binary_otsu[y:int(y + h*0.3), x:int(x + w*0.15)])

            # 在卡片顶部区域进行识别（左上角区域，包含玩家编号）
            card_top = binary_otsu[y:int(y + h*0.3), x:int(x + w*0.15)]

            try:
                if RECOGNITION_MODE == 'ocr':
                    # 使用 OCR 识别
                    results = _recognize_image_ocr(img_gray[y:int(y + h*0.3), x:x + w])
                    if not results:
                        return None
                    return results[0].get('text', '')
                else:
                    # 默认使用模板匹配
                    return _recognize_image_template(card_top)

            except Exception as e:
                print(f"[识别失败] {e}")
                return None
    return None


def extract_player_num(image_path, save_debug=False):
    """
    从图像文件路径提取玩家数字

    Args:
        image_path: 图像文件路径

    Returns:
        str: 识别到的数字，未识别返回 None
        :param image_path:
        :param save_debug:
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        print("图像读取失败")
        return None

    file_name = os.path.basename(image_path)
    return extract_player_num_from_array(img, save_debug=save_debug, debug_prefix=file_name.split(".")[0])


class SpeakerDigitMonitor:
    """发言玩家序号实时监控器"""

    def __init__(self, callback=None, interval=0.5, mode=None):
        """
        初始化监控器

        Args:
            callback: 当检测到digit变化时的回调函数，接收(new_digit, old_digit)参数
            interval: 检测间隔（秒）
            mode: 识别模式，'template' 或 'ocr'，None 表示使用全局默认
        """
        self.callback = callback
        self.interval = interval
        self.mode = mode  # 实例级别的识别模式
        self.current_digit = None
        self.is_running = False
        self.monitor_thread = None
        self._lock = threading.Lock()

    def start(self, capture_func):
        """
        开始监控

        Args:
            capture_func: 截图函数，返回numpy数组（BGR或灰度图像）
        """
        self.is_running = True
        self.capture_func = capture_func
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        current_mode = self.mode if self.mode else RECOGNITION_MODE
        print(f"[SpeakerDigitMonitor] 监控已启动（模式: {current_mode}）")

    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("[SpeakerDigitMonitor] 监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        # 临时设置识别模式
        original_mode = RECOGNITION_MODE
        if self.mode:
            set_recognition_mode(self.mode)

        try:
            while self.is_running:
                try:
                    # 调用截图函数获取画面
                    img = self.capture_func()
                    if img is not None:
                        digit = extract_player_num_from_array(img)

                        with self._lock:
                            old_digit = self.current_digit
                            # digit变化时更新（包括从None变为有值，或值改变）
                            if digit != old_digit and digit is not None:
                                self.current_digit = digit
                                print(f"[SpeakerDigitMonitor] 发言玩家切换: {old_digit} -> {digit}")
                                if self.callback:
                                    self.callback(digit, old_digit)

                except Exception as e:
                    print(f"[SpeakerDigitMonitor] 监控出错: {e}")

                time.sleep(self.interval)
        finally:
            # 恢复原始模式
            if self.mode:
                set_recognition_mode(original_mode)

    def get_current_digit(self):
        """获取当前发言玩家数字"""
        with self._lock:
            return self.current_digit


# 兼容原有测试代码
if __name__ == "__main__":
    # 加载模板
    _load_templates()

    test_imgs_dir = './test_imgs'
    if os.path.exists(test_imgs_dir):
        print(f"当前识别模式: {RECOGNITION_MODE}")
        for ii in os.listdir(test_imgs_dir):
            img_path = os.path.join(test_imgs_dir, ii)
            num = extract_player_num(img_path, save_debug=False)
            print(f'{img_path}：{num}')
    else:
        print(f"测试目录不存在: {test_imgs_dir}")

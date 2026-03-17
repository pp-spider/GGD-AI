import cv2
import numpy as np
import os
import re
import threading
import time
from typing import List, Dict, Optional
from paddleocr import PaddleOCRVL
from paddlex.inference.pipelines.paddleocr_vl.result import PaddleOCRVLResult
from paddlex.inference.pipelines.paddleocr_vl.result import PaddleOCRVLBlock
import time

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# PaddleOCR 模型路径（从 ModelScope 本地缓存加载）
PADDLEOCR_MODEL_PATH = r"C:\Users\spider\.cache\modelscope\hub\models\PaddlePaddle\PaddleOCR-VL-1.5"

# 全局 OCR 识别器（延迟加载）
_ocr_pipeline = None
_ocr_lock = threading.Lock()
_is_loading = False


def _load_ocr_model():
    """延迟加载 PaddleOCR-VL 模型"""
    global _ocr_pipeline, _is_loading

    if _ocr_pipeline is not None:
        return _ocr_pipeline

    with _ocr_lock:
        if _ocr_pipeline is None and not _is_loading:
            _is_loading = True
            try:
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


def _recognize_image(img_array: np.ndarray) -> List[Dict]:
    """
    使用 PaddleOCR-VL 识别图像

    Args:
        img_array: BGR 格式的 numpy 数组

    Returns:
        List[Dict]: 识别结果列表
    """
    pipeline = _load_ocr_model()
    if pipeline is None:
        return []

    # 保存为临时文件
    temp_dir = os.path.join(BASE_DIR, 'temp_images')
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, f'ocr_{int(time.time()*1000)}.png')

    try:
        cv2.imwrite(temp_path, img_array)
        start = time.time()
        output = pipeline.predict(temp_path)
        end = time.time()
        print(f"识别耗时：{end-start}")

        all_texts = []
        for res in output:
            texts = _extract_text_from_result(res)
            all_texts.extend(texts)

        return all_texts
    except Exception as e:
        return None
    # finally:
    #     # 清理临时文件
    #     if os.path.exists(temp_path):
    #         try:
    #             os.remove(temp_path)
    #         except:
    #             pass


def extract_player_num_from_array(img, save_debug=True, debug_prefix=""):
    """
    从图像数组中提取玩家标识（使用 PaddleOCR-VL）

    支持识别数字、汉字、字母等多种字符。

    Args:
        img: 图像 (numpy array, BGR 或灰度)
        save_debug: 是否保存调试图片
        debug_prefix: 调试图片文件名前缀

    Returns:
        str: 识别到的文本，未识别返回 None
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
                cv2.imwrite(os.path.join(temp_dir, f'{debug_prefix}_card_{i}.png'), img_gray[y:y + h, x:x + w])
                cv2.imwrite(os.path.join(temp_dir, f'{debug_prefix}_card_{i}_.png'),
                           img_gray[y:int(y + h*0.3), x:x + w])

            # 在卡片顶部区域进行 OCR 识别（左上角区域，包含玩家编号）
            card_top = img_gray[y:int(y + h*0.3), x:x + w]

            try:
                results = _recognize_image(card_top)

                if not results:
                    return None
                return results[0].get('text', '')

            except Exception as e:
                print(f"[OCR] 识别失败: {e}")
                return None
    return None




def extract_player_num(image_path):
    """
    从图像文件路径提取玩家标识

    Args:
        image_path: 图像文件路径

    Returns:
        str: 识别到的文本，未识别返回 None
    """
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        print("图像读取失败")
        return None

    file_name = os.path.basename(image_path)
    return extract_player_num_from_array(img, save_debug=False, debug_prefix=file_name.split(".")[0])


class SpeakerDigitMonitor:
    """发言玩家标识实时监控器（使用 PaddleOCR-VL）"""

    def __init__(self, callback=None, interval=0.5):
        """
        初始化监控器

        Args:
            callback: 当检测到标识变化时的回调函数，接收(new_id, old_id)参数
            interval: 检测间隔（秒）
        """
        self.callback = callback
        self.interval = interval
        self.current_id = None
        self.is_running = False
        self.monitor_thread = None
        self._lock = threading.Lock()

    def start(self, capture_func):
        """
        开始监控

        Args:
            capture_func: 截图函数，返回 numpy 数组（BGR 格式）
        """
        self.is_running = True
        self.capture_func = capture_func
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print("[SpeakerDigitMonitor] 监控已启动（PaddleOCR-VL 模式）")

    def stop(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print("[SpeakerDigitMonitor] 监控已停止")

    def _monitor_loop(self):
        """监控循环"""
        while self.is_running:
            try:
                img = self.capture_func()
                if img is not None:
                    # 使用 OCR 识别
                    detected_id = extract_player_num_from_array(img)

                    with self._lock:
                        old_id = self.current_id
                        # 标识变化时更新
                        if detected_id != old_id and detected_id is not None:
                            self.current_id = detected_id
                            print(f"[SpeakerDigitMonitor] 发言玩家切换: {old_id} -> {detected_id}")
                            if self.callback:
                                self.callback(detected_id, old_id)

            except Exception as e:
                print(f"[SpeakerDigitMonitor] 监控出错: {e}")

            time.sleep(self.interval)

    def get_current_digit(self):
        """获取当前发言玩家标识"""
        with self._lock:
            return self.current_id


# 兼容原有测试代码
if __name__ == "__main__":
    test_imgs_dir = './test_imgs'
    if os.path.exists(test_imgs_dir):
        for ii in os.listdir(test_imgs_dir):
            img_path = os.path.join(test_imgs_dir, ii)
            result = extract_player_num(img_path)
            print(f'{img_path}：{result}')
    else:
        print(f"测试目录不存在: {test_imgs_dir}")

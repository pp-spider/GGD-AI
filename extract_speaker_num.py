import cv2
import numpy as np
import os
import threading
import time

# 模板路径 - 使用脚本所在目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
template_path = os.path.join(BASE_DIR, 'template_imgs')

# 加载所有模板（全局缓存）
_templates = None

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


def extract_player_num_from_array(img_gray, save_debug=True, debug_prefix=""):
    """
    从灰度图像数组中提取玩家数字

    Args:
        img_gray: 灰度图像 (numpy array)
        save_debug: 是否保存调试图片
        debug_prefix: 调试图片文件名前缀

    Returns:
        str: 识别到的数字 (如 '02', '06')，未识别返回 None
    """
    if img_gray is None or img_gray.size == 0:
        return None

    # 确保是灰度图
    if len(img_gray.shape) == 3:
        img_gray = cv2.cvtColor(img_gray, cv2.COLOR_BGR2GRAY)

    # OTSU二值化
    _, binary_otsu = cv2.threshold(img_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    t_h, t_w = img_gray.shape
    total_square = t_w * t_h

    # 找白色连通域（卡片）
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary_otsu)

    # 加载模板
    templates = _load_templates()
    if not templates:
        print("错误: 没有加载到任何模板")
        return None

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
                           img_gray[y:int(y + h*0.3), x:int(x + w*0.15)])

            # 在卡片顶部区域进行模板匹配
            card_top = img_gray[y:int(y + h*0.3), x:int(x + w*0.15)]

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


def extract_player_num(image_path):
    """
    从图像文件路径提取玩家数字（兼容原有接口）

    Args:
        image_path: 图像文件路径

    Returns:
        str: 识别到的数字，未识别返回 None
    """
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    file_name = os.path.basename(image_path)
    if img is None:
        print("图像读取失败")
        return None
    return extract_player_num_from_array(img, save_debug=False, debug_prefix=file_name.split(".")[0])


class SpeakerDigitMonitor:
    """发言玩家序号实时监控器"""

    def __init__(self, callback=None, interval=0.5):
        """
        初始化监控器

        Args:
            callback: 当检测到digit变化时的回调函数，接收(new_digit, old_digit)参数
            interval: 检测间隔（秒）
        """
        self.callback = callback
        self.interval = interval
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
        print("[SpeakerDigitMonitor] 监控已启动")

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
                        # elif digit is None and old_digit is not None:
                        #     # digit变为None时不更新current_digit，保持最后一个有效值
                        #     print(f"[SpeakerDigitMonitor] 未检测到发言标识，保持当前玩家: {old_digit}")

            except Exception as e:
                print(f"[SpeakerDigitMonitor] 监控出错: {e}")

            time.sleep(self.interval)

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
        for ii in os.listdir(test_imgs_dir):
            num = extract_player_num(f'{test_imgs_dir}/{ii}')
            print(f'{test_imgs_dir}/{ii}：{num}')
    else:
        print(f"测试目录不存在: {test_imgs_dir}")

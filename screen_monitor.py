import numpy as np
import cv2
import win32gui
import win32ui
import win32con
from win32api import GetSystemMetrics
from ctypes import windll, wintypes
from extract_speaker_num import SpeakerDigitMonitor, extract_player_num_from_array


# 使用ctypes定义PrintWindow函数（pywin32可能没有这个函数）
user32 = windll.user32
PrintWindow = user32.PrintWindow
PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
PrintWindow.restype = wintypes.BOOL


class ScreenCapture:
    """屏幕截图器 - 捕获指定窗口的画面"""

    def __init__(self, hwnd=None):
        """
        初始化屏幕截图器

        Args:
            hwnd: 目标窗口句柄，None则捕获整个屏幕
        """
        self.hwnd = hwnd
        self._dc = None
        self._cdc = None
        self._mem_dc = None
        self._bitmap = None
        self._width = 0
        self._height = 0
        self._init_capture()

    def _init_capture(self):
        """初始化截图资源"""
        if self.hwnd:
            # 获取窗口DC
            self._dc = win32gui.GetWindowDC(self.hwnd)
            # 获取窗口客户区大小
            left, top, right, bottom = win32gui.GetClientRect(self.hwnd)
            self._width = right - left
            self._height = bottom - top
        else:
            # 捕获整个屏幕
            self._dc = win32gui.GetDC(0)
            self._width = GetSystemMetrics(0)
            self._height = GetSystemMetrics(1)

        # 创建兼容DC（基于窗口/屏幕DC）
        self._cdc = win32ui.CreateDCFromHandle(self._dc)

        # 创建兼容位图（使用内存DC）
        self._mem_dc = self._cdc.CreateCompatibleDC()
        self._bitmap = win32ui.CreateBitmap()
        self._bitmap.CreateCompatibleBitmap(self._cdc, self._width, self._height)
        self._mem_dc.SelectObject(self._bitmap)

    def capture(self, use_fast_mode=True):
        """
        捕获画面

        Args:
            use_fast_mode: 是否使用快速截图模式（优先使用BitBlt）

        Returns:
            numpy.ndarray: BGR格式的图像数组，失败返回None
        """
        import time
        start_time = time.time()

        try:
            # 执行截图到内存DC
            if self.hwnd:
                if use_fast_mode:
                    # 快速模式：先尝试BitBlt（更快，但要求窗口在前台）
                    try:
                        self._mem_dc.BitBlt((0, 0), (self._width, self._height), self._cdc, (0, 0), win32con.SRCCOPY)
                    except Exception:
                        # BitBlt失败，回退到PrintWindow
                        result = PrintWindow(int(self.hwnd), int(self._mem_dc.GetSafeHdc()), 0)
                        if not result:
                            return None
                else:
                    # 兼容模式：使用PrintWindow（支持后台窗口，但较慢）
                    # PW_RENDERFULLCONTENT = 0x00000002, PW_CLIENTONLY = 0x00000001
                    result = PrintWindow(int(self.hwnd), int(self._mem_dc.GetSafeHdc()), 0)
                    if not result:
                        return None
            else:
                # 截图屏幕
                self._mem_dc.BitBlt((0, 0), (self._width, self._height), self._cdc, (0, 0), win32con.SRCCOPY)

            # 获取位图信息
            bmpinfo = self._bitmap.GetInfo()
            bmpstr = self._bitmap.GetBitmapBits(True)

            # 转换为numpy数组
            img = np.frombuffer(bmpstr, dtype=np.uint8)

            # 根据位图信息确定形状
            if bmpinfo['bmBitsPixel'] == 32:
                img.shape = (self._height, self._width, 4)  # BGRA格式
                # 转换为BGR格式（去掉Alpha通道）
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            elif bmpinfo['bmBitsPixel'] == 24:
                img.shape = (self._height, self._width, 3)  # BGR格式
            else:
                print(f"[ScreenCapture] 不支持的位图格式: {bmpinfo['bmBitsPixel']} bits")
                return None

            elapsed = time.time() - start_time
            if elapsed > 0.1:  # 只记录较慢的截图
                print(f"[ScreenCapture] 截图完成，耗时: {elapsed*1000:.1f}ms")

            return img

        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[ScreenCapture] 截图失败 (耗时: {elapsed*1000:.1f}ms): {e}")
            import traceback
            traceback.print_exc()
            return None

    def release(self):
        """释放资源"""
        if self._bitmap:
            self._bitmap.DeleteObject()
            self._bitmap = None
        if self._mem_dc:
            self._mem_dc.DeleteDC()
            self._mem_dc = None
        if self._cdc:
            self._cdc.DeleteDC()
            self._cdc = None
        if self._dc:
            if self.hwnd:
                win32gui.ReleaseDC(self.hwnd, self._dc)
            else:
                win32gui.ReleaseDC(0, self._dc)
            self._dc = None

    def __del__(self):
        """析构时释放资源"""
        self.release()


class WindowScreenMonitor:
    """窗口画面监控器 - 监控指定窗口的发言玩家标识"""

    def __init__(self, hwnd, on_digit_change=None, interval=0.5):
        """
        初始化窗口监控器

        Args:
            hwnd: 要监控的窗口句柄
            on_digit_change: digit变化时的回调函数，接收(new_digit, old_digit)
            interval: 检测间隔（秒）
        """
        self.hwnd = hwnd
        self.on_digit_change = on_digit_change
        self.interval = interval
        self.screen_capture = None
        self.digit_monitor = None
        self.current_digit = None

    def _capture_func(self):
        """截图函数，供SpeakerDigitMonitor调用"""
        if self.screen_capture:
            return self.screen_capture.capture()
        return None

    def _on_digit_callback(self, new_digit, old_digit):
        """digit变化回调"""
        self.current_digit = new_digit
        if self.on_digit_change:
            self.on_digit_change(new_digit, old_digit)

    def start(self):
        """开始监控"""
        print(f"[WindowScreenMonitor] 开始监控窗口句柄: {self.hwnd}")

        # 初始化截图器
        self.screen_capture = ScreenCapture(self.hwnd)

        # 初始化digit监控器
        self.digit_monitor = SpeakerDigitMonitor(
            callback=self._on_digit_callback,
            interval=self.interval
        )
        self.digit_monitor.start(self._capture_func)

    def stop(self):
        """停止监控"""
        print("[WindowScreenMonitor] 停止监控")
        if self.digit_monitor:
            self.digit_monitor.stop()
        if self.screen_capture:
            self.screen_capture.release()

    def get_current_digit(self):
        """获取当前发言玩家数字"""
        if self.digit_monitor:
            return self.digit_monitor.get_current_digit()
        return None

    def capture_and_detect(self):
        """
        立即截图并检测（用于测试）

        Returns:
            tuple: (image, digit) 截图和检测到的数字
        """
        if not self.screen_capture:
            self.screen_capture = ScreenCapture(self.hwnd)

        img = self.screen_capture.capture()
        if img is not None:
            digit = extract_player_num_from_array(img)
            return img, digit
        return None, None


# 便捷函数
def create_monitor(hwnd, on_digit_change=None, interval=0.5):
    """
    创建窗口监控器

    Args:
        hwnd: 窗口句柄
        on_digit_change: digit变化回调
        interval: 检测间隔

    Returns:
        WindowScreenMonitor: 监控器实例
    """
    return WindowScreenMonitor(hwnd, on_digit_change, interval)


if __name__ == "__main__":
    import cv2
    import time

    # 测试代码
    from window_selector import select_window

    print("请选择要测试的窗口...")
    hwnd, title = select_window()

    if hwnd:
        print(f"测试窗口: {title}")
        monitor = create_monitor(hwnd)
        monitor.start()

        try:
            while True:
                time.sleep(2)
                digit = monitor.get_current_digit()
                print(f"当前发言玩家: {digit}")
        except KeyboardInterrupt:
            print("停止测试")
        finally:
            monitor.stop()
    else:
        print("未选择窗口")

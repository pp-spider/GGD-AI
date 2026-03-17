import tkinter as tk
from tkinter import ttk
import win32gui
import win32con
import threading
import time


class WindowSelector:
    """窗口选择器 - 提供GUI让用户选择要监控的窗口"""

    def __init__(self):
        self.selected_hwnd = None
        self.selected_title = None
        self.root = None

    def _enum_windows_callback(self, hwnd, window_list):
        """枚举窗口回调函数"""
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            title = win32gui.GetWindowText(hwnd)
            # 过滤掉一些系统窗口
            if title and title not in ['Program Manager', '']:
                window_list.append((hwnd, title))
        return True

    def _get_window_list(self):
        """获取所有可见窗口列表"""
        windows = []
        win32gui.EnumWindows(self._enum_windows_callback, windows)
        return windows

    def _on_select(self, event=None):
        """选择窗口"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            self.selected_title = item['values'][1]
            self.selected_hwnd = item['values'][0]
            self.root.destroy()

    def _on_refresh(self):
        """刷新窗口列表"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._populate_list()

    def _populate_list(self):
        """填充窗口列表"""
        windows = self._get_window_list()
        for hwnd, title in windows:
            self.tree.insert('', 'end', values=(hwnd, title))

    def _highlight_window(self, hwnd):
        """高亮显示选中的窗口"""
        try:
            # 获取窗口位置
            rect = win32gui.GetWindowRect(hwnd)
            # 使用闪烁边框高亮
            for _ in range(3):
                win32gui.DrawFocusRect(win32gui.GetDC(0), rect)
                time.sleep(0.1)
                win32gui.InvalidateRect(0, rect, True)
                time.sleep(0.1)
        except:
            pass

    def _on_double_click(self, event):
        """双击选择窗口并高亮"""
        selection = self.tree.selection()
        if selection:
            item = self.tree.item(selection[0])
            hwnd = item['values'][0]
            self._highlight_window(hwnd)
            self._on_select()

    def show_dialog(self):
        """
        显示窗口选择对话框

        Returns:
            tuple: (hwnd, title) 选中的窗口句柄和标题，取消返回 (None, None)
        """
        self.root = tk.Tk()
        self.root.title("选择要监控的游戏窗口")
        self.root.geometry("600x400")
        self.root.resizable(True, True)

        # 标题
        tk.Label(self.root, text="双击选择要监控的窗口", font=('Arial', 12)).pack(pady=10)

        # 创建树形列表
        columns = ('hwnd', 'title')
        self.tree = ttk.Treeview(self.root, columns=columns, show='headings', selectmode='browse')

        # 设置列
        self.tree.heading('hwnd', text='窗口句柄')
        self.tree.heading('title', text='窗口标题')
        self.tree.column('hwnd', width=100)
        self.tree.column('title', width=450)

        # 滚动条
        scrollbar = ttk.Scrollbar(self.root, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # 布局
        self.tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=5)
        scrollbar.pack(side='right', fill='y', pady=5, padx=(0, 10))

        # 绑定双击事件
        self.tree.bind('<Double-1>', self._on_double_click)
        self.tree.bind('<Return>', lambda e: self._on_select())

        # 按钮区域
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="刷新列表", command=self._on_refresh).pack(side='left', padx=5)
        tk.Button(btn_frame, text="选择", command=self._on_select).pack(side='left', padx=5)
        tk.Button(btn_frame, text="取消", command=lambda: self.root.destroy()).pack(side='left', padx=5)

        # 填充列表
        self._populate_list()

        # 居中显示
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

        self.root.mainloop()

        return self.selected_hwnd, self.selected_title


def select_window():
    """
    便捷函数：显示窗口选择对话框

    Returns:
        tuple: (hwnd, title) 或 (None, None)
    """
    selector = WindowSelector()
    return selector.show_dialog()


if __name__ == "__main__":
    hwnd, title = select_window()
    if hwnd:
        print(f"选择的窗口: {title} (句柄: {hwnd})")
    else:
        print("未选择窗口")

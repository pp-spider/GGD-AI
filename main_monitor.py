#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鹅鸭杀游戏发言监控系统主程序

功能：
1. 让用户选择要监控的游戏窗口
2. 实时监控画面获取发言玩家序号（digit）
3. 实时监控语音获取发言内容
4. 当digit变化时，更新语音记录的speaker字段
"""

import sys
import time
import threading
import signal

from window_selector import select_window
from screen_monitor import WindowScreenMonitor
from extract_speaker_statement import GooseGooseDuckAudioAnalyzer


class GooseGooseDuckMonitor:
    """鹅鸭杀游戏监控主控"""

    def __init__(self):
        self.hwnd = None
        self.window_title = None
        self.screen_monitor = None
        self.audio_analyzer = None
        self.is_running = False
        self._lock = threading.Lock()
        self.current_round = 1  # 当前轮数

    def _on_digit_change(self, new_digit, old_digit):
        """
        当画面检测到发言玩家变化时的回调

        Args:
            new_digit: 新的玩家编号，如 '02', '06'
            old_digit: 之前的玩家编号
        """
        print(f"[Main] 发言玩家切换: {old_digit} -> {new_digit}")

        # 更新音频分析器的当前发言玩家（传递当前轮数）
        if self.audio_analyzer:
            self.audio_analyzer.set_speaker(new_digit, self.current_round)

    def _on_new_record(self, record):
        """
        当有新语音记录时的回调

        Args:
            record: 记录字典，包含 timestamp, text, emotion, speaker
        """
        # 可以在这里添加额外的处理，比如实时推送到前端
        pass

    def select_window(self):
        """选择要监控的窗口"""
        print("=" * 50)
        print("请从弹出的窗口列表中选择鹅鸭杀游戏窗口")
        print("=" * 50)

        self.hwnd, self.window_title = select_window()

        if self.hwnd is None:
            print("未选择窗口，程序退出")
            return False

        print(f"已选择窗口: {self.window_title} (句柄: {self.hwnd})")
        return True

    def start(self, preloaded_model=None, round_num: int = 1):
        """启动监控

        Args:
            preloaded_model: 预加载的 FunASR 模型实例（可选，用于避免重复加载模型）
            round_num: 当前轮数，默认为1
        """
        if self.hwnd is None:
            print("错误: 未选择窗口，请先调用select_window()")
            return False

        # 设置当前轮数
        self.current_round = round_num

        print("\n" + "=" * 50)
        print("正在启动监控...")
        print("=" * 50)

        self.is_running = True

        # 1. 初始化音频分析器（使用预加载的模型）
        print("[1/3] 初始化语音监控...")
        self.audio_analyzer = GooseGooseDuckAudioAnalyzer(
            on_new_record=self._on_new_record,
            auto_save=True,
            preloaded_model=preloaded_model
        )

        # 2. 初始化画面监控器
        print("[2/3] 初始化画面监控...")
        self.screen_monitor = WindowScreenMonitor(
            hwnd=self.hwnd,
            on_digit_change=self._on_digit_change,
            interval=0.5  # 每0.5秒检测一次
        )

        # 3. 启动监控线程
        print("[3/3] 启动监控线程...")
        self.audio_analyzer.start()
        self.screen_monitor.start()

        print("\n监控已启动！按 Ctrl+C 停止")
        print("=" * 50)

        return True

    def stop(self):
        """停止监控"""
        print("\n正在停止监控...")
        self.is_running = False

        if self.screen_monitor:
            self.screen_monitor.stop()
            print("[Main] 画面监控已停止")

        if self.audio_analyzer:
            self.audio_analyzer.stop()
            self.audio_analyzer.save_log()
            print("[Main] 语音监控已停止，数据已保存")

        print("[Main] 监控已完全停止")

    def run(self):
        """运行主循环"""
        if not self.select_window():
            return

        if not self.start():
            return

        try:
            # 主循环：显示当前状态
            while self.is_running:
                time.sleep(5)

                current_speaker = None
                if self.audio_analyzer:
                    current_speaker = self.audio_analyzer.get_speaker()

                log_count = 0
                if self.audio_analyzer:
                    log_count = len(self.audio_analyzer.get_conversation_log())

                print(f"[状态] 当前发言玩家: {current_speaker} | 已记录 {log_count} 条对话")

        except KeyboardInterrupt:
            print("\n检测到用户中断")
        finally:
            self.stop()


def main():
    """主函数"""
    print("=" * 50)
    print("鹅鸭杀游戏发言监控系统")
    print("=" * 50)
    print("功能说明:")
    print("1. 选择鹅鸭杀游戏窗口")
    print("2. 系统自动监控画面中的发言玩家标识")
    print("3. 系统自动识别语音内容")
    print("4. 当发言玩家变化时，自动更新记录")
    print("5. 结果保存到 game_analysis.json")
    print("=" * 50)
    print()

    monitor = GooseGooseDuckMonitor()
    monitor.run()

    print("\n程序已退出")


if __name__ == "__main__":
    main()

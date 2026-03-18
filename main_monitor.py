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

import os
import sys
import time
import threading
import signal
from typing import Dict, List, Optional

from window_selector import select_window
from screen_monitor import WindowScreenMonitor, ScreenCapture
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
        self.player_info_map: Dict[str, str] = {}  # 玩家信息映射 (id -> name)
        self._player_info_extracting = False  # 是否正在提取玩家信息
        self.on_player_info_extracted = None  # 玩家信息提取完成回调 (player_info_map) -> None
        self.on_analysis_completed = None  # AI分析完成回调 (analysis_result) -> None
        self._analysis_results: Dict[int, Dict] = {}  # 缓存分析结果 (round -> result)

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

    def _extract_and_cache_player_info(self, run_async: bool = True) -> bool:
        """
        提取并缓存玩家信息

        Args:
            run_async: 是否在后台线程中执行，默认为True

        Returns:
            bool: 是否成功启动提取（异步模式下）或是否成功提取（同步模式下）
        """
        if run_async:
            # 异步模式：在后台线程中执行，不阻塞主流程
            if self._player_info_extracting:
                print("[PlayerInfo] 玩家信息提取已在进行中，跳过")
                return True

            self._player_info_extracting = True
            print("[PlayerInfo] 启动后台线程提取玩家信息...")
            thread = threading.Thread(
                target=self._do_extract_player_info,
                daemon=True
            )
            thread.start()
            return True
        else:
            # 同步模式：直接执行
            return self._do_extract_player_info()

    def _do_extract_player_info(self) -> bool:
        """
        实际执行玩家信息提取（内部方法）

        Returns:
            bool: 是否成功提取
        """
        import time
        start_time = time.time()

        try:
            # 导入提取模块（延迟导入，避免循环依赖）
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from src.player_id_extractor import extract_player_info_kimi

            # 截图
            if not self.screen_monitor:
                self.screen_monitor = WindowScreenMonitor(hwnd=self.hwnd)
                self.screen_monitor.screen_capture = ScreenCapture(self.hwnd)

            print("[PlayerInfo] 开始截图...")
            capture_start = time.time()
            # 使用快速截图模式（优先使用BitBlt）
            img = self.screen_monitor.screen_capture.capture(use_fast_mode=True)
            capture_time = time.time() - capture_start

            if img is None:
                print(f"[PlayerInfo] 截图失败 (耗时: {capture_time:.2f}s)，无法提取玩家信息")
                self._player_info_extracting = False
                return False

            print(f"[PlayerInfo] 截图完成，尺寸: {img.shape}, 耗时: {capture_time:.2f}s")
            print("[PlayerInfo] 正在使用 Kimi AI 提取玩家信息...")
            kimi_start = time.time()
            player_list = extract_player_info_kimi(img, timeout=20.0)  # 设置20秒超时
            kimi_time = time.time() - kimi_start

            with self._lock:
                if player_list:
                    self.player_info_map = {p['id']: p['name'] for p in player_list if p.get('id')}
                    print(f"[PlayerInfo] 已提取 {len(player_list)} 位玩家信息 (Kimi耗时: {kimi_time:.2f}s)")
                    for p in player_list:
                        print(f"  - ID: {p['id']}, 名称: {p['name']}")
                else:
                    print(f"[PlayerInfo] 未能提取到玩家信息（Kimi耗时: {kimi_time:.2f}s，可能超时或API错误）")

            total_time = time.time() - start_time
            print(f"[PlayerInfo] 提取流程总耗时: {total_time:.2f}s")

            # 触发回调通知前端
            if self.on_player_info_extracted:
                try:
                    self.on_player_info_extracted(self.player_info_map.copy())
                except Exception as e:
                    print(f"[PlayerInfo] 回调执行失败: {e}")

            self._player_info_extracting = False
            return bool(player_list)

        except Exception as e:
            total_time = time.time() - start_time
            print(f"[PlayerInfo] 提取玩家信息失败 (总耗时: {total_time:.2f}s): {e}")
            self._player_info_extracting = False
            return False

    def force_extract_player_info(self) -> bool:
        """
        强制重新提取玩家信息（公开接口，同步执行）

        Returns:
            bool: 是否成功提取
        """
        return self._extract_and_cache_player_info(run_async=False)

    def get_player_name(self, player_id: str) -> Optional[str]:
        """
        获取玩家名称

        Args:
            player_id: 玩家ID（如 "01", "02"）

        Returns:
            Optional[str]: 玩家名称，如果没有则返回None
        """
        # 尝试直接匹配
        if player_id in self.player_info_map:
            return self.player_info_map[player_id]

        # 尝试去除前导零匹配
        normalized_id = player_id.lstrip('0') or '0'
        for pid, name in self.player_info_map.items():
            if pid.lstrip('0') or '0' == normalized_id:
                return name

        return None

    def start(self, preloaded_model=None, round_num: int = 1, extract_players: bool = True):
        """启动监控

        Args:
            preloaded_model: 预加载的 FunASR 模型实例（可选，用于避免重复加载模型）
            round_num: 当前轮数，默认为1
            extract_players: 是否提取玩家信息，默认为True（仅在首次启动时提取）
        """
        if self.hwnd is None:
            print("错误: 未选择窗口，请先调用select_window()")
            return False

        # 设置当前轮数
        self.current_round = round_num

        # 新增：首次启动时异步提取玩家信息（不阻塞监控启动）
        if extract_players and not self.player_info_map and not self._player_info_extracting:
            self._extract_and_cache_player_info(run_async=True)

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
            # 停止录音并触发最后剩余语音的识别（传入当前轮数）
            self.audio_analyzer.stop(round_num=self.current_round)
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

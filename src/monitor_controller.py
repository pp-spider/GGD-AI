#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
鹅鸭杀游戏监控控制器

功能：
1. 封装GooseGooseDuckMonitor监控逻辑
2. 添加WebSocket支持，实时推送事件
3. 管理游戏轮数
4. 提供线程安全的操作接口
5. 与api_server.py的WebSocket连接管理协同工作
"""

import threading
import logging
import asyncio
from typing import Callable, Optional, Dict, Any, List
from datetime import datetime
import sys
import os

# 添加父目录到路径以导入现有模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main_monitor import GooseGooseDuckMonitor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GooseGooseDuckMonitorController:
    """
    鹅鸭杀游戏监控控制器

    封装监控逻辑，添加WebSocket支持，管理游戏轮数
    与api_server.py的ConnectionManager协同工作
    """

    def __init__(self, websocket_callback: Optional[Callable[[Dict[str, Any]], None]] = None):
        """
        初始化监控控制器

        Args:
            websocket_callback: WebSocket回调函数，接收事件字典
        """
        self.monitor = GooseGooseDuckMonitor()
        self.websocket_callback = websocket_callback
        self.current_round = 1
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        self._records_lock = threading.Lock()
        self._is_running = False

        logger.info("[MonitorController] 控制器初始化完成")

    def set_websocket_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        设置WebSocket回调函数

        Args:
            callback: 回调函数，接收事件字典
        """
        self.websocket_callback = callback
        logger.info("[MonitorController] WebSocket回调已设置")

    def _send_websocket_message(self, message: Dict[str, Any]):
        """
        发送WebSocket消息（线程安全）

        Args:
            message: 消息字典，包含type和data字段
        """
        if self.websocket_callback:
            try:
                self.websocket_callback(message)
                logger.debug(f"[MonitorController] WebSocket消息已发送: {message['type']}")
            except Exception as e:
                logger.error(f"[MonitorController] WebSocket消息发送失败: {e}")

    def _on_digit_change(self, new_digit: str, old_digit: str):
        """
        玩家切换时触发

        Args:
            new_digit: 新的玩家编号
            old_digit: 之前的玩家编号
        """
        logger.info(f"[MonitorController] 玩家切换: {old_digit} -> {new_digit}")

        # 调用原有逻辑（更新音频分析器的当前发言玩家，传递轮数）
        if self.monitor.audio_analyzer:
            self.monitor.audio_analyzer.set_speaker(new_digit, self.current_round)

        # 推送WebSocket消息
        self._send_websocket_message({
            "type": "speaker_change",
            "data": {
                "from": old_digit,
                "to": new_digit,
                "round": self.current_round,
                "timestamp": datetime.now().isoformat()
            }
        })

    def _on_new_record(self, record: Dict[str, Any]):
        """
        新记录时触发

        Args:
            record: 记录字典，包含timestamp, text, emotion, speaker等字段
        """
        # 添加轮数信息
        record_with_round = record.copy()
        record_with_round["round"] = self.current_round

        # 保存到本地记录
        with self._records_lock:
            self._records.append(record_with_round)

        logger.info(f"[MonitorController] 新记录: 玩家{record.get('speaker')} - {record.get('text', '')[:30]}...")

        # 推送WebSocket消息
        self._send_websocket_message({
            "type": "record",
            "data": record_with_round
        })

    def start(self, hwnd: int, round_num: int = 1) -> bool:
        """
        开始监控

        Args:
            hwnd: 窗口句柄
            round_num: 初始轮数，默认为1

        Returns:
            bool: 是否成功启动
        """
        logger.info(f"[MonitorController] 开始启动监控，窗口句柄: {hwnd}, 轮数: {round_num}")

        with self._lock:
            if self._is_running:
                logger.warning("[MonitorController] 监控已在运行中")
                return True

            # 设置轮数
            self.current_round = round_num

            # 设置窗口句柄
            self.monitor.hwnd = hwnd

            # 重写monitor的回调
            self.monitor._on_digit_change = self._on_digit_change

            # 启动监控（这会初始化audio_analyzer）
            result = self.monitor.start()

            if result and self.monitor.audio_analyzer:
                # 设置音频分析器的回调
                self.monitor.audio_analyzer.on_new_record = self._on_new_record
                logger.info("[MonitorController] 音频分析器回调已设置")

            if result:
                self._is_running = True
                # 发送状态消息
                self._send_websocket_message({
                    "type": "status",
                    "data": {
                        "status": "started",
                        "current_round": self.current_round,
                        "hwnd": hwnd,
                        "timestamp": datetime.now().isoformat()
                    }
                })
                logger.info("[MonitorController] 监控启动成功")
            else:
                logger.error("[MonitorController] 监控启动失败")
                # 发送错误消息
                self._send_websocket_message({
                    "type": "error",
                    "data": {
                        "message": "监控启动失败",
                        "timestamp": datetime.now().isoformat()
                    }
                })

            return result

    def stop(self) -> bool:
        """
        停止监控

        Returns:
            bool: 是否成功停止
        """
        logger.info("[MonitorController] 停止监控")

        with self._lock:
            if not self._is_running:
                return True

            try:
                self.monitor.stop()
                self._is_running = False

                # 发送状态消息
                self._send_websocket_message({
                    "type": "status",
                    "data": {
                        "status": "stopped",
                        "current_round": self.current_round,
                        "total_records": len(self._records),
                        "timestamp": datetime.now().isoformat()
                    }
                })

                logger.info("[MonitorController] 监控已停止")
                return True
            except Exception as e:
                logger.error(f"[MonitorController] 停止监控失败: {e}")
                # 发送错误消息
                self._send_websocket_message({
                    "type": "error",
                    "data": {
                        "message": f"停止监控失败: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    }
                })
                return False

    def next_round(self):
        """
        进入下一轮
        """
        with self._lock:
            self.current_round += 1
            new_round = self.current_round

        logger.info(f"[MonitorController] 进入第 {new_round} 轮")

        # 推送WebSocket消息
        self._send_websocket_message({
            "type": "status",
            "data": {
                "event": "round_change",
                "current_round": new_round,
                "timestamp": datetime.now().isoformat()
            }
        })

    def reset_round(self, round_num: int = 1):
        """
        重置轮数

        Args:
            round_num: 重置到的轮数，默认为1
        """
        with self._lock:
            old_round = self.current_round
            self.current_round = round_num

        logger.info(f"[MonitorController] 轮数重置: {old_round} -> {round_num}")

        # 推送WebSocket消息
        self._send_websocket_message({
            "type": "status",
            "data": {
                "event": "round_reset",
                "current_round": round_num,
                "previous_round": old_round,
                "timestamp": datetime.now().isoformat()
            }
        })

    def get_records(self) -> List[Dict[str, Any]]:
        """
        获取所有记录

        Returns:
            List[Dict[str, Any]]: 记录列表
        """
        with self._records_lock:
            return self._records.copy()

    def get_current_round(self) -> int:
        """
        获取当前轮数

        Returns:
            int: 当前轮数
        """
        with self._lock:
            return self.current_round

    def get_current_speaker(self) -> Optional[str]:
        """
        获取当前发言玩家

        Returns:
            Optional[str]: 当前发言玩家编号，如果没有则返回None
        """
        if self.monitor.audio_analyzer:
            return self.monitor.audio_analyzer.get_speaker()
        return None

    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态

        Returns:
            Dict[str, Any]: 状态字典
        """
        with self._lock:
            return {
                "is_running": self._is_running,
                "current_round": self.current_round,
                "current_speaker": self.get_current_speaker(),
                "total_records": len(self._records),
                "hwnd": self.monitor.hwnd
            }

    def clear_records(self):
        """
        清空所有记录
        """
        with self._records_lock:
            self._records = []

        logger.info("[MonitorController] 记录已清空")

        # 推送WebSocket消息
        self._send_websocket_message({
            "type": "status",
            "data": {
                "event": "records_cleared",
                "current_round": self.current_round,
                "timestamp": datetime.now().isoformat()
            }
        })

    def is_running(self) -> bool:
        """
        检查监控是否正在运行

        Returns:
            bool: 是否正在运行
        """
        with self._lock:
            return self._is_running


# 与api_server.py集成的适配器
class WebSocketManagerAdapter:
    """
    WebSocket管理器适配器

    用于将监控控制器与api_server.py的ConnectionManager集成
    """

    def __init__(self, connection_manager):
        """
        初始化适配器

        Args:
            connection_manager: api_server.py中的ConnectionManager实例
        """
        self.manager = connection_manager

    async def async_callback(self, message: Dict[str, Any]):
        """
        异步回调函数

        Args:
            message: 消息字典
        """
        await self.manager.broadcast(message)

    def get_sync_callback(self) -> Callable[[Dict[str, Any]], None]:
        """
        获取同步回调函数（用于在同步代码中调用）

        Returns:
            Callable: 同步回调函数
        """
        def sync_callback(message: Dict[str, Any]):
            # 使用asyncio.create_task在事件循环中执行异步广播
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.manager.broadcast(message))
                else:
                    loop.run_until_complete(self.manager.broadcast(message))
            except RuntimeError:
                # 如果没有事件循环，创建一个新的
                asyncio.run(self.manager.broadcast(message))

        return sync_callback


if __name__ == "__main__":
    # 测试代码
    def test_websocket_callback(message):
        print(f"[WebSocket Test] {message}")

    controller = GooseGooseDuckMonitorController(websocket_callback=test_websocket_callback)

    print("控制器测试模式")
    print(f"当前状态: {controller.get_status()}")
    print(f"当前轮数: {controller.get_current_round()}")

    # 测试轮数切换
    controller.next_round()
    controller.next_round()
    print(f"当前轮数: {controller.get_current_round()}")

    # 测试重置轮数
    controller.reset_round(1)
    print(f"当前轮数: {controller.get_current_round()}")

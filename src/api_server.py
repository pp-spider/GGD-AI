#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GGD-AI FastAPI HTTP/WebSocket服务

提供REST API和WebSocket实时通信接口
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
import logging
import sys
import os
from datetime import datetime
import queue
import threading
from contextlib import asynccontextmanager

# 添加父目录到路径以导入现有模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_monitor import GooseGooseDuckMonitor
from window_selector import select_window
from extract_speaker_statement import GooseGooseDuckAudioAnalyzer
from funasr import AutoModel
from src.ai_game_analyzer import analyze_game_round, get_analyzer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时设置事件循环并启动事件处理器
    set_event_loop(asyncio.get_event_loop())
    # 启动后台任务处理事件队列
    asyncio.create_task(process_events())
    logger.info("事件处理器已启动")
    yield
    # 关闭时清理
    logger.info("应用关闭")

app = FastAPI(
    title="GGD-AI API",
    description="鹅鸭杀游戏发言监控系统的API服务",
    version="1.0.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420", "tauri://localhost", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 数据模型 ============

class StartMonitoringRequest(BaseModel):
    """开始监控请求"""
    round: Optional[int] = 1
    auto_save: Optional[bool] = True


class WindowInfo(BaseModel):
    """窗口信息"""
    hwnd: int
    title: str


class Record(BaseModel):
    """语音记录"""
    timestamp: str
    text: str
    emotion: str
    speaker: str
    duration: float


class StatusResponse(BaseModel):
    """状态响应"""
    status: str
    is_running: bool
    current_speaker: Optional[str]
    record_count: int
    window_title: Optional[str]
    current_round: int = 1


class PlayerInfo(BaseModel):
    """玩家信息"""
    id: str
    name: str


class PlayerListResponse(BaseModel):
    """玩家列表响应"""
    status: str
    players: List[PlayerInfo]
    count: int


class AIAnalysisRequest(BaseModel):
    """AI分析请求"""
    round: Optional[int] = None  # 要分析的轮数，None表示当前轮


class PlayerAnalysisData(BaseModel):
    """玩家分析数据"""
    playerId: str
    playerName: str
    identityGuess: str  # "goose", "duck", "neutral", "unknown"
    confidence: float
    reasoning: str
    suspiciousPoints: List[str]
    trustworthyPoints: List[str]


class RelationshipData(BaseModel):
    """关系数据"""
    from_player: str
    to_player: str
    relation_type: str  # "ally", "enemy", "neutral", "suspicious"
    evidence: str


class AIAnalysisResponse(BaseModel):
    """AI分析响应"""
    status: str
    analysis: Optional[Dict[str, Any]] = None
    timestamp: str
    message: Optional[str] = None


# ============ WebSocket连接管理器 ============

class ConnectionManager:
    """WebSocket连接管理器"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket连接建立，当前连接数: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket连接断开，当前连接数: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"发送消息失败: {e}")
                disconnected.append(connection)

        # 清理断开的连接
        async with self._lock:
            for conn in disconnected:
                if conn in self.active_connections:
                    self.active_connections.remove(conn)

    async def send_to(self, websocket: WebSocket, message: dict):
        """发送消息给指定连接"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"发送消息失败: {e}")


manager = ConnectionManager()

# ============ 线程安全事件队列 ============
# 用于从同步回调（后台线程）向异步主循环传递事件
event_queue = queue.Queue()
event_loop = None  # 将在初始化时设置

def set_event_loop(loop):
    """设置事件循环，供后台线程使用"""
    global event_loop
    event_loop = loop

def broadcast_digit_change_sync(new_digit, old_digit):
    """同步版本：将发言玩家变化事件放入队列"""
    try:
        event_queue.put({
            "type": "speaker_change",
            "data": {
                "new_speaker": new_digit,
                "old_speaker": old_digit,
                "timestamp": datetime.now().isoformat()
            }
        })
    except Exception as e:
        logger.error(f"队列添加事件失败: {e}")

def broadcast_new_record_sync(record):
    """同步版本：将新记录事件放入队列"""
    try:
        logger.info(f"[WebSocket] 准备广播新记录: speaker={record.get('speaker')}, text={record.get('text', '')[:30]}...")
        event_queue.put({
            "type": "new_record",
            "data": record
        })
        logger.info("[WebSocket] 事件已加入队列")
    except Exception as e:
        logger.error(f"队列添加事件失败: {e}")

async def process_events():
    """处理事件队列中的事件"""
    logger.info("[EventProcessor] 事件处理器启动")
    while True:
        try:
            # 非阻塞方式检查队列
            while not event_queue.empty():
                event = event_queue.get_nowait()
                logger.info(f"[EventProcessor] 处理事件: {event.get('type')}")
                await manager.broadcast(event)
                logger.info(f"[EventProcessor] 事件已广播")
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"[EventProcessor] 处理事件失败: {e}")

        await asyncio.sleep(0.1)  # 每100ms检查一次


# ============ 监控控制器 ============

class MonitorController:
    """监控控制器 - 封装GooseGooseDuckMonitor"""

    def __init__(self):
        self.monitor: Optional[GooseGooseDuckMonitor] = None
        self.is_initialized = False
        self.current_round = 1
        self._lock = asyncio.Lock()
        self._preloaded_model = None  # 预加载的 FunASR 模型（只加载一次）
        self._latest_analysis: Optional[Dict[str, Any]] = None  # 最新分析结果
        self._is_analyzing = False  # 是否正在分析

    async def trigger_ai_analysis(self, round_num: Optional[int] = None):
        """触发AI分析"""
        async with self._lock:
            if self._is_analyzing:
                logger.info("[AI分析] 分析已在进行中，跳过")
                return

            if not self.monitor or not self.monitor.audio_analyzer:
                logger.warning("[AI分析] 监控器未初始化，无法分析")
                return

            self._is_analyzing = True
            target_round = round_num or self.current_round

        try:
            # 广播分析开始
            await manager.broadcast({
                "type": "ai_analysis_started",
                "data": {"round": target_round, "timestamp": datetime.now().isoformat()}
            })
            logger.info(f"[AI分析] 开始分析第{target_round}轮")

            # 获取记录和玩家信息
            records = self.monitor.audio_analyzer.get_conversation_log()
            # 过滤指定轮次的记录
            round_records = [r for r in records if r.get("round", 1) == target_round]

            if not round_records:
                logger.warning(f"[AI分析] 第{target_round}轮无记录")
                await manager.broadcast({
                    "type": "ai_analysis_completed",
                    "data": {
                        "round": target_round,
                        "status": "empty",
                        "message": "本轮无发言记录"
                    }
                })
                return

            # 转换玩家信息格式
            players_data = [
                {"id": pid, "name": name}
                for pid, name in self.monitor.player_info_map.items()
            ]

            # 如果没有玩家信息，使用记录中的speaker
            if not players_data:
                speaker_ids = set(r.get("speaker", "?") for r in round_records if r.get("speaker"))
                players_data = [{"id": sid, "name": f"玩家{sid}"} for sid in speaker_ids]

            logger.info(f"[AI分析] 分析数据：{len(round_records)}条记录，{len(players_data)}位玩家")

            # 执行分析
            analysis_result = await analyze_game_round(
                records_data=round_records,
                players_data=players_data,
                round_num=target_round
            )

            # 保存结果
            self._latest_analysis = analysis_result

            # 广播分析完成
            await manager.broadcast({
                "type": "ai_analysis_completed",
                "data": {
                    "round": target_round,
                    "status": "success",
                    "analysis": analysis_result
                }
            })
            logger.info(f"[AI分析] 第{target_round}轮分析完成")

        except Exception as e:
            logger.error(f"[AI分析] 分析失败: {e}")
            await manager.broadcast({
                "type": "ai_analysis_error",
                "data": {
                    "round": target_round,
                    "status": "error",
                    "message": str(e)
                }
            })
        finally:
            self._is_analyzing = False

    def _on_player_info_extracted(self, player_info_map: Dict[str, str]):
        """
        玩家信息提取完成回调
        通过事件队列广播到 WebSocket
        """
        if not player_info_map:
            return

        players = [
            {"id": pid, "name": name}
            for pid, name in player_info_map.items()
        ]

        logger.info(f"[PlayerInfo] 提取完成，共 {len(players)} 位玩家，准备广播")

        # 通过事件队列广播（线程安全）
        try:
            event_queue.put({
                "type": "player_info_update",
                "data": {
                    "players": players,
                    "count": len(players),
                    "timestamp": datetime.now().isoformat()
                }
            })
            logger.info("[PlayerInfo] 玩家信息更新事件已加入队列")

            # 如果监控已停止且有记录，触发AI分析
            if self.monitor and not self.monitor.is_running:
                records = self.monitor.audio_analyzer.get_conversation_log() if self.monitor.audio_analyzer else []
                if records:
                    logger.info("[PlayerInfo] 监控已停止且有记录，触发AI分析")
                    # 使用asyncio.create_task在事件循环中执行
                    if event_loop:
                        asyncio.run_coroutine_threadsafe(
                            self.trigger_ai_analysis(self.current_round),
                            event_loop
                        )
        except Exception as e:
            logger.error(f"[PlayerInfo] 广播玩家信息失败: {e}")

    async def init(self) -> bool:
        """初始化系统 - 预加载语音识别模型（只加载一次）"""
        async with self._lock:
            if self.is_initialized:
                return True

            try:
                logger.info("开始预加载语音识别模型...")
                # 在后台线程中加载模型，避免阻塞主线程
                loop = asyncio.get_event_loop()
                self._preloaded_model = await loop.run_in_executor(
                    None, self._load_model
                )
                logger.info("语音识别模型预加载完成，后续可重复使用")

                self.monitor = GooseGooseDuckMonitor()

                # 设置玩家信息提取完成回调
                self.monitor.on_player_info_extracted = self._on_player_info_extracted

                self.is_initialized = True
                logger.info("监控控制器初始化完成")
                return True
            except Exception as e:
                logger.error(f"初始化失败: {e}")
                return False

    def _load_model(self):
        """在后台线程加载模型（只执行一次）"""
        try:
            logger.info("正在加载 FunASR 模型到内存...")
            # 直接加载模型，不创建 audio analyzer
            model = AutoModel(
                model="paraformer-zh",
                vad_model="fsmn-vad",
                punc_model="ct-punc",
            )
            logger.info("FunASR 模型加载完成")
            return model
        except Exception as e:
            logger.error(f"模型加载失败: {e}")
            raise

    async def select_window(self) -> Optional[WindowInfo]:
        """选择窗口"""
        async with self._lock:
            if not self.is_initialized:
                raise HTTPException(status_code=400, detail="系统未初始化")

            try:
                # 在后台线程中运行GUI选择
                loop = asyncio.get_event_loop()
                hwnd, title = await loop.run_in_executor(None, select_window)

                if hwnd is None:
                    return None

                self.monitor.hwnd = hwnd
                self.monitor.window_title = title

                return WindowInfo(hwnd=hwnd, title=title)
            except Exception as e:
                logger.error(f"选择窗口失败: {e}")
                raise HTTPException(status_code=500, detail=f"选择窗口失败: {str(e)}")

    async def start(self, round_num: int = 1, auto_save: bool = True) -> bool:
        """开始监控"""
        async with self._lock:
            if not self.is_initialized:
                raise HTTPException(status_code=400, detail="系统未初始化")

            if self.monitor.hwnd is None:
                raise HTTPException(status_code=400, detail="未选择窗口")

            if self.monitor.is_running:
                return True

            try:
                self.current_round = round_num

                # 重写回调函数以支持WebSocket广播（使用线程安全的队列）
                original_on_digit_change = self.monitor._on_digit_change
                original_on_new_record = self.monitor._on_new_record

                # 包装回调 - 使用同步版本，将事件放入队列
                def on_digit_change_wrapper(new_digit, old_digit):
                    original_on_digit_change(new_digit, old_digit)
                    broadcast_digit_change_sync(new_digit, old_digit)

                def on_new_record_wrapper(record):
                    logger.info(f"[MonitorCallback] 收到新记录: speaker={record.get('speaker')}, text={record.get('text', '')[:20]}...")
                    broadcast_new_record_sync(record)
                    # 调用原始回调
                    if original_on_new_record:
                        logger.info("[MonitorCallback] 调用原始回调")
                        original_on_new_record(record)

                self.monitor._on_digit_change = on_digit_change_wrapper
                self.monitor._on_new_record = on_new_record_wrapper

                # 在后台线程中启动监控，传入预加载的模型
                loop = asyncio.get_event_loop()

                # 模型应该已经预加载，如果没有则报错
                if self._preloaded_model is None:
                    logger.error("模型未预加载，请先调用 init()")
                    raise HTTPException(status_code=500, detail="模型未预加载")

                result = await loop.run_in_executor(
                    None,
                    lambda: self.monitor.start(preloaded_model=self._preloaded_model, round_num=round_num)
                )

                # 监控启动后，设置 audio_analyzer 的回调（因为 start 会创建新的 audio_analyzer 实例）
                if result and self.monitor.audio_analyzer:
                    logger.info("设置 audio_analyzer 的 on_new_record 回调")
                    self.monitor.audio_analyzer.on_new_record = on_new_record_wrapper

                logger.info("监控已启动，模型保持加载状态供下次复用")

                if result:
                    await manager.broadcast({
                        "type": "status_change",
                        "data": {"status": "running", "round": round_num}
                    })
                    logger.info(f"监控已启动，轮数: {round_num}")
                    return True
                return False

            except Exception as e:
                logger.error(f"启动监控失败: {e}")
                raise HTTPException(status_code=500, detail=f"启动监控失败: {str(e)}")

    async def stop(self) -> bool:
        """停止监控"""
        async with self._lock:
            if not self.monitor or not self.monitor.is_running:
                return True

            try:
                loop = asyncio.get_event_loop()
                logger.info("[Stop] 开始停止监控...")

                # 执行停止（包含最后一段语音的识别）
                await loop.run_in_executor(None, self.monitor.stop)
                logger.info("[Stop] 监控核心已停止")

                # 短暂等待，确保最后一段语音的WebSocket消息被处理
                logger.info("[Stop] 等待WebSocket消息处理...")
                await asyncio.sleep(0.5)

                # 广播停止状态
                await manager.broadcast({
                    "type": "status_change",
                    "data": {"status": "stopped"}
                })
                logger.info("[Stop] 停止状态已广播")

                # 检查是否有记录，如果有则触发AI分析
                if self.monitor.audio_analyzer:
                    records = self.monitor.audio_analyzer.get_conversation_log()
                    round_records = [r for r in records if r.get("round", 1) == self.current_round]
                    if round_records:
                        logger.info(f"[Stop] 第{self.current_round}轮有{len(round_records)}条记录，触发AI分析")
                        # 异步触发分析，不阻塞stop响应
                        asyncio.create_task(self.trigger_ai_analysis(self.current_round))

                # 模型保持加载状态，下次启动直接复用
                logger.info("[Stop] 监控完全停止")
                return True
            except Exception as e:
                logger.error(f"[Stop] 停止监控失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise HTTPException(status_code=500, detail=f"停止监控失败: {str(e)}")

    def get_records(self) -> List[Dict[str, Any]]:
        """获取所有记录"""
        if self.monitor and self.monitor.audio_analyzer:
            return self.monitor.audio_analyzer.get_conversation_log()
        return []

    def get_status(self) -> StatusResponse:
        """获取当前状态"""
        if not self.monitor:
            return StatusResponse(
                status="not_initialized",
                is_running=False,
                current_speaker=None,
                record_count=0,
                window_title=None,
                current_round=1
            )

        current_speaker = None
        record_count = 0

        if self.monitor.audio_analyzer:
            current_speaker = self.monitor.audio_analyzer.get_speaker()
            record_count = len(self.monitor.audio_analyzer.get_conversation_log())

        return StatusResponse(
            status="running" if self.monitor.is_running else "ready",
            is_running=self.monitor.is_running,
            current_speaker=current_speaker,
            record_count=record_count,
            window_title=self.monitor.window_title,
            current_round=self.current_round
        )

    async def reset_round(self, round_num: int = 1):
        """重置轮数"""
        async with self._lock:
            self.current_round = round_num

            # 广播重置事件
            await manager.broadcast({
                "type": "round_reset",
                "data": {"round": round_num, "timestamp": datetime.now().isoformat()}
            })

            logger.info(f"轮数已重置为: {round_num}")
            return {"round": round_num, "message": "轮数已重置"}


# 全局监控控制器实例
controller = MonitorController()


# ============ API端点 ============

@app.get("/")
async def root():
    """根路径 - API信息"""
    return {
        "name": "GGD-AI API",
        "version": "1.0.0",
        "description": "鹅鸭杀游戏发言监控系统API"
    }


@app.get("/api/status")
async def get_status():
    """获取系统状态"""
    return controller.get_status()


@app.post("/api/init")
async def init_system():
    """初始化系统，加载模型"""
    result = await controller.init()
    if result:
        return {"status": "success", "message": "系统初始化完成"}
    raise HTTPException(status_code=500, detail="系统初始化失败")


@app.post("/api/select-window")
async def select_monitor_window():
    """选择要监控的窗口"""
    window_info = await controller.select_window()
    if window_info:
        return {
            "status": "success",
            "window": window_info.dict()
        }
    return {"status": "cancelled", "message": "用户取消选择"}


@app.post("/api/start")
async def start_monitoring(data: StartMonitoringRequest):
    """开始监听"""
    # 如果未选择窗口，自动弹出选择器
    if controller.monitor.hwnd is None:
        logger.info("未选择窗口，自动弹出选择器...")
        window_info = await controller.select_window()
        if window_info is None:
            return {"status": "cancelled", "message": "用户取消选择窗口"}

    result = await controller.start(
        round_num=data.round,
        auto_save=data.auto_save
    )
    if result:
        return {
            "status": "success",
            "message": "监控已启动",
            "round": data.round,
            "window_title": controller.monitor.window_title
        }
    raise HTTPException(status_code=500, detail="启动监控失败")


@app.post("/api/stop")
async def stop_monitoring():
    """停止监听"""
    result = await controller.stop()
    if result:
        return {"status": "success", "message": "监控已停止"}
    raise HTTPException(status_code=500, detail="停止监控失败")


@app.get("/api/records")
async def get_records():
    """获取历史记录"""
    records = controller.get_records()
    return {
        "status": "success",
        "count": len(records),
        "records": records
    }


@app.post("/api/reset")
async def reset_round(data: dict = None):
    """重置轮数"""
    round_num = data.get("round", 1) if data else 1
    result = await controller.reset_round(round_num)
    return result


@app.post("/api/clear-records")
async def clear_records():
    """清空记录"""
    if controller.monitor and controller.monitor.audio_analyzer:
        controller.monitor.audio_analyzer.conversation_log = []
        return {"status": "success", "message": "记录已清空"}
    return {"status": "success", "message": "无需清空"}


@app.get("/api/players")
async def get_players():
    """获取当前提取的玩家信息列表"""
    if controller.monitor and controller.monitor.player_info_map:
        players = [
            {"id": pid, "name": name}
            for pid, name in controller.monitor.player_info_map.items()
        ]
        return {"status": "success", "players": players, "count": len(players)}
    return {"status": "empty", "players": [], "count": 0}


@app.post("/api/extract-players")
async def force_extract_players():
    """强制重新提取玩家信息（异步执行，不阻塞）"""
    if not controller.monitor:
        raise HTTPException(status_code=400, detail="系统未初始化")
    if controller.monitor.hwnd is None:
        raise HTTPException(status_code=400, detail="未选择窗口")

    # 检查是否正在提取中
    if controller.monitor._player_info_extracting:
        return {"status": "pending", "message": "玩家信息提取正在进行中"}

    # 启动后台线程异步提取（不阻塞API响应）
    # 提取完成后会通过 WebSocket 自动广播 player_info_update 事件
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: controller.monitor._extract_and_cache_player_info(run_async=True)
    )

    return {"status": "started", "message": "玩家信息提取已启动，请等待 WebSocket 通知"}


@app.post("/api/analyze")
async def analyze_game(data: AIAnalysisRequest):
    """触发AI分析指定轮次"""
    round_num = data.round or controller.current_round

    # 异步触发分析
    asyncio.create_task(controller.trigger_ai_analysis(round_num))

    return {
        "status": "started",
        "message": f"第{round_num}轮AI分析已启动",
        "round": round_num,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/analysis/{round}")
async def get_analysis(round: int):
    """获取指定轮次的分析结果"""
    analyzer = get_analyzer()
    result = analyzer.get_cached_result(round)

    if result:
        return {
            "status": "success",
            "analysis": {
                "round": result.round,
                "timestamp": result.timestamp,
                "playerAnalysis": [
                    {
                        "playerId": p.playerId,
                        "playerName": p.playerName,
                        "identityGuess": p.identityGuess,
                        "confidence": p.confidence,
                        "reasoning": p.reasoning,
                        "suspiciousPoints": p.suspiciousPoints,
                        "trustworthyPoints": p.trustworthyPoints
                    }
                    for p in result.playerAnalysis
                ],
                "relationshipMap": [
                    {
                        "from": r.from_player,
                        "to": r.to_player,
                        "type": r.relation_type,
                        "evidence": r.evidence
                    }
                    for r in result.relationshipMap
                ],
                "summary": result.summary
            },
            "timestamp": datetime.now().isoformat()
        }

    return {
        "status": "not_found",
        "analysis": None,
        "message": f"第{round}轮的分析结果不存在",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/analysis/latest")
async def get_latest_analysis():
    """获取最新分析结果"""
    if controller._latest_analysis:
        return {
            "status": "success",
            "analysis": controller._latest_analysis,
            "timestamp": datetime.now().isoformat()
        }

    # 尝试从分析器缓存获取
    analyzer = get_analyzer()
    result = analyzer.get_cached_result(controller.current_round)

    if result:
        return {
            "status": "success",
            "analysis": {
                "round": result.round,
                "timestamp": result.timestamp,
                "playerAnalysis": [
                    {
                        "playerId": p.playerId,
                        "playerName": p.playerName,
                        "identityGuess": p.identityGuess,
                        "confidence": p.confidence,
                        "reasoning": p.reasoning,
                        "suspiciousPoints": p.suspiciousPoints,
                        "trustworthyPoints": p.trustworthyPoints
                    }
                    for p in result.playerAnalysis
                ],
                "relationshipMap": [
                    {
                        "from": r.from_player,
                        "to": r.to_player,
                        "type": r.relation_type,
                        "evidence": r.evidence
                    }
                    for r in result.relationshipMap
                ],
                "summary": result.summary
            },
            "timestamp": datetime.now().isoformat()
        }

    return {
        "status": "not_found",
        "analysis": None,
        "message": "暂无分析结果",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/analysis-status")
async def get_analysis_status():
    """获取AI分析状态"""
    return {
        "status": "success",
        "is_analyzing": controller._is_analyzing,
        "current_round": controller.current_round,
        "timestamp": datetime.now().isoformat()
    }


# ============ WebSocket端点 ============

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket实时通信端点"""
    await manager.connect(websocket)

    try:
        # 发送当前状态
        status = controller.get_status()
        await manager.send_to(websocket, {
            "type": "status",
            "data": status.dict()
        })

        while True:
            try:
                # 接收消息
                data = await websocket.receive_text()
                message = json.loads(data)

                msg_type = message.get("type")

                if msg_type == "ping":
                    await manager.send_to(websocket, {"type": "pong"})

                elif msg_type == "get_status":
                    status = controller.get_status()
                    await manager.send_to(websocket, {
                        "type": "status",
                        "data": status.dict()
                    })

                elif msg_type == "get_records":
                    records = controller.get_records()
                    await manager.send_to(websocket, {
                        "type": "records",
                        "data": records
                    })

                else:
                    await manager.send_to(websocket, {
                        "type": "error",
                        "message": f"未知消息类型: {msg_type}"
                    })

            except json.JSONDecodeError:
                await manager.send_to(websocket, {
                    "type": "error",
                    "message": "无效的JSON格式"
                })

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket错误: {e}")
        await manager.disconnect(websocket)


# ============ 启动入口 ============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=9876)

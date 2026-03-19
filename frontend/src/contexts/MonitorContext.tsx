import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";
import type { AIAnalysisResult } from "../types/analysis";

const API_BASE = "http://localhost:9876";

export interface Record {
  id: number;
  timestamp: string;
  text: string;
  emotion: string;
  speaker: string;
  duration: number;
  round: number;
}

export interface PlayerInfo {
  id: string;
  name: string;
}

interface MonitorContextValue {
  status: string;
  isMonitoring: boolean;
  currentRound: number;
  currentSpeaker: string | null;
  windowTitle: string | null;
  records: Record[];
  players: PlayerInfo[];
  myPlayerId: string | null;
  // AI分析相关
  analysisResult: AIAnalysisResult | null;
  isAnalyzing: boolean;
  setMyPlayerId: (id: string) => void;
  getPlayerDisplayName: (speakerId: string | null) => string | null;
  initSystem: () => Promise<any>;
  startMonitor: () => Promise<void>;
  stopMonitor: () => Promise<void>;
  fetchPlayers: () => Promise<void>;
  forceExtractPlayers: () => Promise<void>;
  startAnalysis: (round?: number) => Promise<void>;
  fetchLatestAnalysis: () => Promise<void>;
}

const MonitorContext = createContext<MonitorContextValue | null>(null);

export function MonitorProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState("正在加载语音识别模型...");
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [currentRound, setCurrentRound] = useState(1);
  const [currentSpeaker, setCurrentSpeaker] = useState<string | null>(null);
  const [records, setRecords] = useState<Record[]>([]);
  const [windowTitle, setWindowTitle] = useState<string | null>(null);
  const [players, setPlayers] = useState<PlayerInfo[]>([]);
  const [myPlayerId, setMyPlayerIdState] = useState<string | null>(null);
  // AI分析相关状态
  const [analysisResult, setAnalysisResult] = useState<AIAnalysisResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const nextIdRef = useRef(1);
  // 用于防止 StrictMode 双重渲染导致重复连接
  const isConnectingRef = useRef(false);
  // 用于去重 - 存储已处理的消息标识
  const processedMessagesRef = useRef<Set<string>>(new Set());

  console.log("[MonitorContext] 状态 - 记录数:", records.length, "当前玩家:", currentSpeaker, "currentRound:", currentRound);

  // 追踪组件挂载和 currentRound 变化
  useEffect(() => {
    console.log("[MonitorContext] 组件挂载/重新渲染, currentRound:", currentRound);
  }, []);

  useEffect(() => {
    console.log("[MonitorContext] currentRound 变化:", currentRound);
  }, [currentRound]);

  // 从 localStorage 读取自己的玩家ID
  useEffect(() => {
    const savedPlayerId = localStorage.getItem("ggd_ai_my_player_id");
    if (savedPlayerId) {
      setMyPlayerIdState(savedPlayerId);
      console.log("[MonitorContext] 从localStorage读取玩家ID:", savedPlayerId);
    }
  }, []);

  // 初始化系统
  const initSystem = useCallback(async () => {
    console.log("[MonitorContext] 开始初始化系统..., currentRound:", currentRound);
    try {
      const response = await fetch(`${API_BASE}/api/init`, { method: "POST" });
      const data = await response.json();
      console.log("[MonitorContext] init API 响应:", data);

      if (data.status === "loading") {
        setStatus(`正在加载语音识别模型... ${data.progress}%`);
        await new Promise((resolve) => setTimeout(resolve, 1000));
        return initSystem();
      }

      setStatus("系统就绪");
      connectWebSocket();
      return data;
    } catch (error) {
      console.error("[MonitorContext] 初始化失败:", error);
      setStatus("连接失败，请检查后端服务是否启动");
      throw error;
    }
  }, []);

  // 连接 WebSocket
  const connectWebSocket = useCallback(() => {
    // 防止重复连接
    if (isConnectingRef.current) {
      console.log("[MonitorContext] WebSocket 正在连接中，跳过");
      return;
    }

    // 如果已有连接，先关闭
    if (wsRef.current) {
      console.log("[MonitorContext] 关闭旧 WebSocket 连接");
      wsRef.current.close();
      wsRef.current = null;
    }

    isConnectingRef.current = true;
    console.log("[MonitorContext] 正在连接 WebSocket...");
    const ws = new WebSocket(`ws://localhost:9876/ws`);

    ws.onopen = () => {
      console.log("[MonitorContext] WebSocket 连接成功");
      isConnectingRef.current = false;
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      console.log("[MonitorContext] 收到 WebSocket 消息:", msg.type, msg);

      // 为消息生成唯一标识用于去重 (基于类型、时间戳、内容和发言者)
      if (msg.type === "new_record" || msg.type === "record") {
        const msgKey = `${msg.type}-${msg.data?.timestamp}-${msg.data?.speaker}-${msg.data?.text?.slice(0, 20)}`;

        if (processedMessagesRef.current.has(msgKey)) {
          console.log("[MonitorContext] 重复消息，跳过:", msgKey);
          return;
        }

        processedMessagesRef.current.add(msgKey);
        // 限制集合大小，防止内存泄漏
        if (processedMessagesRef.current.size > 1000) {
          const iterator = processedMessagesRef.current.values();
          processedMessagesRef.current.delete(iterator.next().value as string);
        }

        console.log("[MonitorContext] 新发言记录 - 添加到列表:", msg.data);
        const newRecord: Record = {
          id: nextIdRef.current++,
          timestamp: msg.data.timestamp || new Date().toLocaleTimeString(),
          text: msg.data.text || "",
          emotion: msg.data.emotion || "neutral",
          speaker: msg.data.speaker || "?",
          duration: msg.data.duration || 0,
          round: msg.data.round || currentRound,
        };
        setRecords((prev) => {
          const updated = [...prev, newRecord];
          console.log("[MonitorContext] 记录列表更新:", updated.length, "条");
          return updated;
        });
      } else if (msg.type === "status") {
        console.log("[MonitorContext] 状态更新:", msg.data);
        setIsMonitoring(msg.data.is_running);
        setCurrentSpeaker(msg.data.current_speaker);
        if (msg.data.current_round != null) {
          console.log("[MonitorContext] status消息设置currentRound:", msg.data.current_round);
          setCurrentRound(msg.data.current_round);
        }
      } else if (msg.type === "speaker_change") {
        console.log("[MonitorContext] 发言玩家切换:", msg.data);
        setCurrentSpeaker(msg.data.new_speaker || msg.data.to);
      } else if (msg.type === "status_change") {
        console.log("[MonitorContext] 状态变化:", msg.data);
        setIsMonitoring(msg.data.status === "running");
        if (msg.data.round != null) {
          console.log("[MonitorContext] status_change消息设置currentRound:", msg.data.round);
          setCurrentRound(msg.data.round);
        }
      } else if (msg.type === "round_reset") {
        const newRound = msg.data.round || msg.data.current_round || 1;
        console.log("[MonitorContext] 轮数重置:", msg.data, "设置currentRound:", newRound);
        setCurrentRound(newRound);
      } else if (msg.type === "player_info_update") {
        console.log("[MonitorContext] 玩家信息更新:", msg.data);
        if (msg.data.players) {
          setPlayers(msg.data.players);
        }
      } else if (msg.type === "ai_analysis_started") {
        console.log("[MonitorContext] AI分析开始:", msg.data);
        setIsAnalyzing(true);
      } else if (msg.type === "ai_analysis_completed") {
        console.log("[MonitorContext] AI分析完成:", msg.data);
        setIsAnalyzing(false);
        if (msg.data.status === "success" && msg.data.analysis) {
          setAnalysisResult(msg.data.analysis);
        }
      } else if (msg.type === "ai_analysis_error") {
        console.log("[MonitorContext] AI分析错误:", msg.data);
        setIsAnalyzing(false);
      }
    };

    ws.onclose = (event) => {
      console.log("[MonitorContext] WebSocket 断开:", event.code, event.reason);
      isConnectingRef.current = false;
      // 只有在不是正常关闭且监控还在运行的情况下才重连
      if (event.code !== 1000 && event.code !== 1001) {
        setTimeout(() => {
          isConnectingRef.current = false;
          connectWebSocket();
        }, 3000);
      }
    };

    ws.onerror = (error) => {
      console.error("[MonitorContext] WebSocket 错误:", error);
      isConnectingRef.current = false;
    };

    wsRef.current = ws;
  }, [currentRound]);

  // 获取玩家信息
  const fetchPlayers = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/players`);
      const data = await response.json();
      if (data.status === "success") {
        setPlayers(data.players);
        console.log("[MonitorContext] 已获取玩家信息:", data.players);
      }
    } catch (e) {
      console.error("[MonitorContext] 获取玩家信息失败:", e);
    }
  }, []);

  // 强制提取玩家信息（异步执行，结果通过 WebSocket 通知）
  const forceExtractPlayers = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/extract-players`, {
        method: "POST",
      });
      const data = await response.json();
      console.log("[MonitorContext] 强制提取玩家信息已启动:", data);
      // 注意：提取结果将通过 WebSocket 的 player_info_update 事件通知
    } catch (e) {
      console.error("[MonitorContext] 强制提取玩家信息失败:", e);
    }
  }, []);

  // 开始监听
  const startMonitor = useCallback(async () => {
    console.log("[MonitorContext] 开始监听流程..., 当前currentRound:", currentRound);

    try {
      const requestRound = currentRound;
      console.log("[MonitorContext] 发送启动命令... 请求body中round:", requestRound, "(与当前一致)");
      const startResponse = await fetch(`${API_BASE}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ round: requestRound, auto_save: true }),
      });
      const startData = await startResponse.json();
      console.log("[MonitorContext] 启动命令结果:", startData);

      if (startData.status === "success") {
        console.log("[MonitorContext] 启动成功，保持currentRound不变, 当前:", currentRound);
        setIsMonitoring(true);
        if (startData.window_title) {
          setWindowTitle(startData.window_title);
        }
        // 注意：玩家信息会异步提取，完成后通过 WebSocket 的 player_info_update 事件通知
        console.log("[MonitorContext] 监听启动完成，玩家信息后台提取中...");
      } else {
        console.error("[MonitorContext] 启动失败:", startData);
      }
    } catch (error) {
      console.error("[MonitorContext] 启动监听失败:", error);
    }
  }, [currentRound]);

  // 停止监听
  const stopMonitor = useCallback(async () => {
    console.log("[MonitorContext] 停止监听...");
    try {
      const response = await fetch(`${API_BASE}/api/stop`, { method: "POST" });
      const data = await response.json();
      console.log("[MonitorContext] 停止结果:", data);
      setIsMonitoring(false);
      setCurrentSpeaker(null);
      // 停止后会自动触发AI分析，无需手动调用
      // 递增轮次，为下一轮做准备
      setCurrentRound((prev) => {
        const nextRound = prev + 1;
        console.log("[MonitorContext] 停止后递增轮次:", prev, "->", nextRound);
        return nextRound;
      });
    } catch (error) {
      console.error("[MonitorContext] 停止监听失败:", error);
    }
  }, []);

  // 手动触发AI分析
  const startAnalysis = useCallback(async (round?: number) => {
    console.log("[MonitorContext] 触发AI分析...", round);
    try {
      const response = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ round }),
      });
      const data = await response.json();
      console.log("[MonitorContext] 分析触发结果:", data);
    } catch (error) {
      console.error("[MonitorContext] 触发AI分析失败:", error);
    }
  }, []);

  // 获取最新分析结果
  const fetchLatestAnalysis = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/analysis/latest`);
      const data = await response.json();
      if (data.status === "success" && data.analysis) {
        console.log("[MonitorContext] 获取到最新分析结果:", data.analysis);
        setAnalysisResult(data.analysis);
      }
    } catch (error) {
      console.error("[MonitorContext] 获取分析结果失败:", error);
    }
  }, []);

  // 设置自己的玩家ID
  const setMyPlayerId = useCallback((id: string) => {
    setMyPlayerIdState(id);
    localStorage.setItem("ggd_ai_my_player_id", id);
    console.log("[MonitorContext] 设置玩家ID:", id);
  }, []);

  // 获取玩家显示名称
  const getPlayerDisplayName = useCallback((speakerId: string | null): string | null => {
    if (!speakerId) return null;

    const player = players.find((p) => p.id === speakerId);
    if (player) {
      const isSelf = myPlayerId === speakerId;
      return `${player.id} ${player.name}${isSelf ? " (自己)" : ""}`;
    }

    // 没找到玩家，返回默认格式
    return `${speakerId}玩家`;
  }, [players, myPlayerId]);

  // 清理 WebSocket
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const value: MonitorContextValue = {
    status,
    isMonitoring,
    currentRound,
    currentSpeaker,
    windowTitle,
    records,
    players,
    myPlayerId,
    // AI分析相关
    analysisResult,
    isAnalyzing,
    setMyPlayerId,
    getPlayerDisplayName,
    initSystem,
    startMonitor,
    stopMonitor,
    fetchPlayers,
    forceExtractPlayers,
    startAnalysis,
    fetchLatestAnalysis,
  };

  return (
    <MonitorContext.Provider value={value}>
      {children}
    </MonitorContext.Provider>
  );
}

export function useMonitor(): MonitorContextValue {
  const context = useContext(MonitorContext);
  if (!context) {
    throw new Error("useMonitor must be used within a MonitorProvider");
  }
  return context;
}

export type { MonitorContextValue };

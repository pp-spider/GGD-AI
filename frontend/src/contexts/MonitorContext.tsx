import React, { createContext, useContext, useState, useCallback, useRef, useEffect } from "react";

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

interface MonitorContextValue {
  status: string;
  isMonitoring: boolean;
  currentRound: number;
  currentSpeaker: string | null;
  windowTitle: string | null;
  records: Record[];
  initSystem: () => Promise<any>;
  startMonitor: () => Promise<void>;
  stopMonitor: () => Promise<void>;
}

const MonitorContext = createContext<MonitorContextValue | null>(null);

export function MonitorProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState("正在加载语音识别模型...");
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [currentRound, setCurrentRound] = useState(0);
  const [currentSpeaker, setCurrentSpeaker] = useState<string | null>(null);
  const [records, setRecords] = useState<Record[]>([]);
  const [windowTitle, setWindowTitle] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const nextIdRef = useRef(1);
  // 用于防止 StrictMode 双重渲染导致重复连接
  const isConnectingRef = useRef(false);
  // 用于去重 - 存储已处理的消息标识
  const processedMessagesRef = useRef<Set<string>>(new Set());

  console.log("[MonitorContext] 状态 - 记录数:", records.length, "当前玩家:", currentSpeaker);

  // 初始化系统
  const initSystem = useCallback(async () => {
    console.log("[MonitorContext] 开始初始化系统...");
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
          processedMessagesRef.current.delete(iterator.next().value);
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
        if (msg.data.current_round) {
          setCurrentRound(msg.data.current_round);
        }
      } else if (msg.type === "speaker_change") {
        console.log("[MonitorContext] 发言玩家切换:", msg.data);
        setCurrentSpeaker(msg.data.new_speaker || msg.data.to);
      } else if (msg.type === "status_change") {
        console.log("[MonitorContext] 状态变化:", msg.data);
        setIsMonitoring(msg.data.status === "running");
        if (msg.data.round) {
          setCurrentRound(msg.data.round);
        }
      } else if (msg.type === "round_reset") {
        console.log("[MonitorContext] 轮数重置:", msg.data);
        setCurrentRound(msg.data.round || msg.data.current_round || 1);
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

  // 开始监听
  const startMonitor = useCallback(async () => {
    console.log("[MonitorContext] 开始监听流程...");

    try {
      console.log("[MonitorContext] 发送启动命令...");
      const startResponse = await fetch(`${API_BASE}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ round: currentRound + 1, auto_save: true }),
      });
      const startData = await startResponse.json();
      console.log("[MonitorContext] 启动命令结果:", startData);

      if (startData.status === "success") {
        setCurrentRound((prev) => prev + 1);
        setIsMonitoring(true);
        if (startData.window_title) {
          setWindowTitle(startData.window_title);
        }
        console.log("[MonitorContext] 监听启动完成");
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
    } catch (error) {
      console.error("[MonitorContext] 停止监听失败:", error);
    }
  }, []);

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
    initSystem,
    startMonitor,
    stopMonitor,
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

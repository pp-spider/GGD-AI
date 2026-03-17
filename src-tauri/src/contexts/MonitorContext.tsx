import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { useWebSocket } from '../hooks/useWebSocket';

export interface Record {
  id: string;
  timestamp: string;
  text: string;
  speaker: string;
  emotion: 'suspicious' | 'trust' | 'neutral';
  round: number;
  duration?: number;
}

interface MonitorContextValue {
  isMonitoring: boolean;
  currentRound: number;
  currentSpeaker: string | null;
  records: Record[];
  wsConnected: boolean;
  isLoading: boolean;
  error: string | null;
  start: () => Promise<boolean>;
  stop: () => Promise<boolean>;
  toggle: () => Promise<boolean>;
  reset: () => Promise<boolean>;
  nextRound: () => Promise<boolean>;
  clearRecords: () => Promise<boolean>;
  selectWindow: () => Promise<{hwnd: number; title: string} | null>;
}

const MonitorContext = createContext<MonitorContextValue | null>(null);

const API_BASE_URL = 'http://127.0.0.1:9876/api';

export function MonitorProvider({ children }: { children: React.ReactNode }) {
  const { status: wsStatus, messages, sendMessage } = useWebSocket('ws://127.0.0.1:9876/ws');

  const [isMonitoring, setIsMonitoring] = useState(false);
  const [currentRound, setCurrentRound] = useState(1);
  const [currentSpeaker, setCurrentSpeaker] = useState<string | null>(null);
  const [records, setRecords] = useState<Record[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 使用 ref 来避免闭包问题
  const currentRoundRef = useRef(currentRound);
  currentRoundRef.current = currentRound;

  // 处理WebSocket消息
  useEffect(() => {
    if (messages.length === 0) return;

    const latestMessage = messages[messages.length - 1];
    console.log('[MonitorContext] 收到WebSocket消息:', latestMessage);

    switch (latestMessage.type) {
      case 'record':
      case 'new_record':
        const recordData = latestMessage.data;
        const newRecord: Record = {
          id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: recordData?.timestamp || new Date().toLocaleTimeString(),
          text: recordData?.text || '',
          speaker: recordData?.speaker || '未知',
          emotion: recordData?.emotion || 'neutral',
          round: recordData?.round || currentRoundRef.current,
          duration: recordData?.duration
        };
        console.log('[MonitorContext] 添加新记录:', newRecord);
        setRecords(prev => [...prev, newRecord]);
        break;

      case 'speaker_change':
        const speakerData = latestMessage.data;
        console.log('[MonitorContext] 玩家切换:', speakerData);
        setCurrentSpeaker(speakerData?.to || speakerData?.new_speaker || null);
        break;

      case 'status_change':
        const statusData = latestMessage.data;
        console.log('[MonitorContext] 状态变化:', statusData);
        setIsMonitoring(statusData?.status === 'running');
        break;

      case 'status':
        const status = latestMessage.data;
        console.log('[MonitorContext] 状态更新:', status);
        setIsMonitoring(status?.is_running || status?.monitoring || false);
        setCurrentSpeaker(status?.current_speaker || null);
        if (status?.current_round) {
          setCurrentRound(status.current_round);
        }
        break;

      case 'round_reset':
        const roundData = latestMessage.data;
        console.log('[MonitorContext] 轮数重置:', roundData);
        setCurrentRound(roundData?.round || roundData?.current_round || 1);
        break;

      case 'error':
        console.error('[MonitorContext] 错误:', latestMessage);
        setError(latestMessage.message || latestMessage.data?.message || '未知错误');
        break;
    }
  }, [messages]);

  // API调用
  const apiCall = useCallback(async (endpoint: string, method: string = 'GET', body?: object) => {
    try {
      setError(null);
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || '请求失败');
      }

      return await response.json();
    } catch (e: any) {
      setError(e.message);
      throw e;
    }
  }, []);

  // 选择窗口
  const selectWindow = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await apiCall('/select-window', 'POST');
      setIsLoading(false);
      return result.status === 'success' ? result.window : null;
    } catch (e) {
      setIsLoading(false);
      return null;
    }
  }, [apiCall]);

  // 开始监听
  const start = useCallback(async () => {
    setIsLoading(true);
    try {
      const newRound = currentRound;
      await apiCall('/start', 'POST', { round: newRound, auto_save: true });
      setIsMonitoring(true);
      setCurrentRound(newRound);
      setIsLoading(false);
      return true;
    } catch (e) {
      setIsLoading(false);
      return false;
    }
  }, [apiCall, isMonitoring, currentRound]);

  // 停止监听
  const stop = useCallback(async () => {
    setIsLoading(true);
    try {
      await apiCall('/stop', 'POST');
      setIsMonitoring(false);
      setIsLoading(false);
      return true;
    } catch (e) {
      setIsLoading(false);
      return false;
    }
  }, [apiCall]);

  // 切换监听状态
  const toggle = useCallback(async () => {
    if (isMonitoring) {
      return await stop();
    } else {
      return await start();
    }
  }, [isMonitoring, start, stop]);

  // 重置轮数
  const reset = useCallback(async () => {
    try {
      await apiCall('/reset', 'POST', { round: 1 });
      setCurrentRound(1);
      setRecords([]);
      return true;
    } catch (e) {
      return false;
    }
  }, [apiCall]);

  // 下一轮
  const nextRound = useCallback(async () => {
    try {
      const newRound = currentRound + 1;
      await apiCall('/reset', 'POST', { round: newRound });
      setCurrentRound(newRound);
      return true;
    } catch (e) {
      return false;
    }
  }, [apiCall, currentRound]);

  // 清空记录
  const clearRecords = useCallback(async () => {
    try {
      await apiCall('/clear-records', 'POST');
      setRecords([]);
      return true;
    } catch (e) {
      return false;
    }
  }, [apiCall]);

  const value: MonitorContextValue = {
    isMonitoring,
    currentRound,
    currentSpeaker,
    records,
    wsConnected: wsStatus.connected,
    isLoading,
    error,
    start,
    stop,
    toggle,
    reset,
    nextRound,
    clearRecords,
    selectWindow
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
    throw new Error('useMonitor must be used within a MonitorProvider');
  }
  return context;
}

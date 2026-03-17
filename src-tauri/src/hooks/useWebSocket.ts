import { useEffect, useRef, useState, useCallback } from 'react';

interface WebSocketMessage {
  type: 'record' | 'speaker_change' | 'status' | 'error';
  data: any;
}

interface UseWebSocketReturn {
  connected: boolean;
  messages: WebSocketMessage[];
  sendMessage: (message: any) => void;
  disconnect: () => void;
}

const RECONNECT_DELAY = 3000;
const HEARTBEAT_INTERVAL = 30000;

export function useWebSocket(url: string): UseWebSocketReturn {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const ws = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
  const heartbeatTimer = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnect = useRef(true);

  // 清除定时器
  const clearTimers = useCallback(() => {
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
  }, []);

  // 连接WebSocket
  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      const socket = new WebSocket(url);

      socket.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
        shouldReconnect.current = true;

        // 启动心跳检测
        heartbeatTimer.current = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          }
        }, HEARTBEAT_INTERVAL);
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // 忽略心跳响应
          if (data.type === 'pong') {
            return;
          }

          const message: WebSocketMessage = {
            type: data.type || 'status',
            data: data
          };

          setMessages((prev) => [...prev, message]);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      socket.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        clearTimers();

        // 自动重连
        if (shouldReconnect.current) {
          reconnectTimer.current = setTimeout(() => {
            console.log('Attempting to reconnect...');
            connect();
          }, RECONNECT_DELAY);
        }
      };

      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      ws.current = socket;
    } catch (error) {
      console.error('Failed to connect WebSocket:', error);
    }
  }, [url, clearTimers]);

  // 发送消息
  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not connected');
    }
  }, []);

  // 断开连接
  const disconnect = useCallback(() => {
    shouldReconnect.current = false;
    clearTimers();

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }
    setConnected(false);
  }, [clearTimers]);

  // 初始化连接
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    connected,
    messages,
    sendMessage,
    disconnect
  };
}

import { useCallback, useEffect, useState } from 'react';
import MessageList from './MessageList';
import ToggleButton from './ToggleButton';
import { useMonitor } from '../contexts/MonitorContext';

export interface Message {
  id: string;
  round: number;
  speaker: string;
  content: string;
  emotion: 'suspicious' | 'trust' | 'neutral';
  timestamp: number;
}

function MainScreen() {
  const {
    isMonitoring,
    currentRound,
    currentSpeaker,
    records,
    wsConnected,
    isLoading,
    error,
    toggle,
    selectWindow
  } = useMonitor();

  const [showWindowSelect, setShowWindowSelect] = useState(false);

  // 转换records为messages格式
  const messages: Message[] = records.map(record => ({
    id: `${record.timestamp}-${Math.random().toString(36).substr(2, 9)}`,
    round: record.round,
    speaker: `${record.speaker}玩家`,
    content: record.text,
    emotion: record.emotion,
    timestamp: new Date(record.timestamp).getTime()
  }));

  const handleToggle = useCallback(async () => {
    if (!isMonitoring) {
      // 开始监听前需要选择窗口
      setShowWindowSelect(true);
      const window = await selectWindow();
      setShowWindowSelect(false);

      if (window) {
        await toggle();
      }
    } else {
      await toggle();
    }
  }, [isMonitoring, toggle, selectWindow]);


  return (
    <div className="main-screen">
      <div className="main-header">
        <h1 className="app-title">鹅鸭杀发言监听助手</h1>
        <div className="header-right">
          <div className={`ws-status ${wsConnected ? 'connected' : 'disconnected'}`} />
          <div className="round-info">第 {currentRound} 轮</div>
        </div>
      </div>

      {currentSpeaker && (
        <div className="current-speaker">
          <span className="speaker-label">当前发言:</span>
          <span className="speaker-value">{currentSpeaker}玩家</span>
        </div>
      )}

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      {showWindowSelect && (
        <div className="overlay">
          <div className="overlay-text">请选择游戏窗口...</div>
        </div>
      )}

      <MessageList messages={messages} />

      <div className="main-controls">
        <ToggleButton
          isListening={isMonitoring}
          onToggle={handleToggle}
          disabled={isLoading || showWindowSelect}
        />
      </div>
    </div>
  );
}

export default MainScreen;

import React, { useRef, useEffect } from "react";
import { useMonitor } from "../hooks/useMonitor";

const MainScreen: React.FC = () => {
  const { isMonitoring, startMonitor, stopMonitor, currentRound, currentSpeaker, records } = useMonitor();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  console.log("[MainScreen] 渲染 - 当前记录数:", records.length, "当前玩家:", currentSpeaker);

  // 自动滚动到底部
  useEffect(() => {
    console.log("[MainScreen] 记录数变化:", records.length, "自动滚动");
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [records]);

  const handleToggleMonitor = async () => {
    console.log("[MainScreen] 点击按钮, 当前状态:", isMonitoring);
    if (isMonitoring) {
      await stopMonitor();
    } else {
      await startMonitor();
    }
  };

  // 按轮数分组记录
  const groupedRecords = records.reduce((acc, record) => {
    if (!acc[record.round]) acc[record.round] = [];
    acc[record.round].push(record);
    return acc;
  }, {} as Record<number, typeof records>);

  console.log("[MainScreen] 分组记录:", Object.keys(groupedRecords), "轮");

  return (
    <div className="main-screen">
      <div className="title-bar">
        <span>🎮 鹅鸭杀发言监听助手</span>
        {currentSpeaker && (
          <span className="current-speaker">🔊 {currentSpeaker}玩家发言中...</span>
        )}
      </div>

      <div className="messages-container">
        {records.length === 0 && (
          <div style={{ textAlign: "center", color: "rgba(255,255,255,0.5)", padding: "20px" }}>
            暂无发言记录
          </div>
        )}

        {Object.entries(groupedRecords).map(([round, roundRecords]) => (
          <div key={round} className="round-group">
            <div className="round-divider">第{round}轮</div>
            {roundRecords.map((record) => (
              <div key={record.id} className="message-item">
                <div className="message-header">
                  <span className="speaker-badge">{record.speaker}玩家</span>
                  <span className="timestamp">{record.timestamp}</span>
                </div>
                <div className="message-text">{record.text}</div>
              </div>
            ))}
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      <div className="control-panel">
        <button
          className={`control-btn ${isMonitoring ? "btn-stop" : "btn-start"}`}
          onClick={handleToggleMonitor}
        >
          {isMonitoring ? "⏸ 结束监听" : "▶ 开始监听"}
        </button>
        <div className="round-info">当前: 第{currentRound}轮</div>
      </div>
    </div>
  );
};

export default MainScreen;

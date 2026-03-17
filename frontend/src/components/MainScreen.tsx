import React, { useRef, useEffect } from "react";
import { useMonitor } from "../hooks/useMonitor";

const MainScreen: React.FC = () => {
  const {
    isMonitoring,
    startMonitor,
    stopMonitor,
    currentSpeaker,
    windowTitle,
    records,
  } = useMonitor();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  console.log(
    "[MainScreen] 渲染 - 当前记录数:",
    records.length,
    "当前玩家:",
    currentSpeaker
  );

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

  // 格式化窗口标题，截取主要部分
  const formatWindowTitle = (title: string | null) => {
    if (!title) return "未选择窗口";
    // 如果包含 "Goose Goose Duck"，简化为游戏名
    if (title.includes("Goose Goose Duck")) return "Goose Goose Duck";
    if (title.includes("鹅鸭杀")) return "鹅鸭杀";
    // 否则返回前15个字符
    return title.length > 15 ? title.slice(0, 15) + "..." : title;
  };

  return (
    <div className="main-screen">
      {/* 标题栏 - 显示窗口名称和当前发言玩家 */}
      <div className="title-bar">
        <div className="title-content">
          <span className="window-name">
            {formatWindowTitle(windowTitle)}
          </span>
          {currentSpeaker && (
            <span className="current-speaker">
              🔊 {currentSpeaker}玩家发言中
            </span>
          )}
        </div>
      </div>

      <div className="messages-container">
        {records.length === 0 && (
          <div
            style={{
              textAlign: "center",
              color: "rgba(255,255,255,0.5)",
              padding: "40px 20px",
            }}
          >
            点击"开始监听"开始识别游戏发言
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
      </div>
    </div>
  );
};

export default MainScreen;

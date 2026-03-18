import React, { useState, useEffect } from "react";

interface SetupScreenProps {
  onComplete: (playerId: string) => void;
  initialValue?: string;
}

const SetupScreen: React.FC<SetupScreenProps> = ({ onComplete, initialValue }) => {
  const [playerId, setPlayerId] = useState<string>("");
  const [error, setError] = useState<string>("");

  // 从 localStorage 读取上次输入的值
  useEffect(() => {
    const savedId = localStorage.getItem("ggd_ai_my_player_id");
    if (initialValue) {
      setPlayerId(initialValue);
    } else if (savedId) {
      setPlayerId(savedId);
    }
  }, [initialValue]);

  // 验证输入是否为有效的玩家ID (01-16)
  const validateInput = (value: string): boolean => {
    if (!value) return false;
    const num = parseInt(value, 10);
    return num >= 1 && num <= 16;
  };

  // 处理输入变化
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    let value = e.target.value;

    // 只允许数字
    value = value.replace(/[^0-9]/g, "");

    // 限制为2位数字
    if (value.length > 2) {
      value = value.slice(0, 2);
    }

    setPlayerId(value);
    setError("");
  };

  // 处理确认
  const handleConfirm = () => {
    if (!playerId) {
      setError("请输入玩家ID");
      return;
    }

    if (!validateInput(playerId)) {
      setError("请输入01-16之间的数字");
      return;
    }

    // 格式化为2位数字
    const formattedId = playerId.padStart(2, "0");

    // 保存到 localStorage
    localStorage.setItem("ggd_ai_my_player_id", formattedId);

    // 调用回调
    onComplete(formattedId);
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      handleConfirm();
    }
  };

  return (
    <div className="setup-screen">
      <div className="setup-card">
        <h2 className="setup-title">设置玩家ID</h2>
        <p className="setup-description">请输入您的游戏座位号 (01-16)</p>

        <input
          type="text"
          value={playerId}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          placeholder="例如: 01"
          className="setup-input"
          maxLength={2}
          autoFocus
        />

        {error && <div className="setup-error">{error}</div>}

        <button
          className="setup-btn"
          onClick={handleConfirm}
          disabled={!playerId}
        >
          确认
        </button>
      </div>
    </div>
  );
};

export default SetupScreen;

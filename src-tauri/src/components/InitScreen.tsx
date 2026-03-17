import { useState, useEffect } from 'react';

interface InitScreenProps {
  error?: string | null;
}

function InitScreen({ error }: InitScreenProps) {
  const [progress, setProgress] = useState(0);
  const [statusText, setStatusText] = useState('正在连接后端服务...');

  useEffect(() => {
    const interval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          return 100;
        }
        return prev + 1;
      });
    }, 100);

    // 更新状态文字
    const statusInterval = setInterval(() => {
      setStatusText((prev) => {
        if (prev.includes('连接')) return '正在加载语音识别模型...';
        if (prev.includes('语音识别')) return '正在初始化监控服务...';
        return '正在等待服务就绪...';
      });
    }, 2000);

    return () => {
      clearInterval(interval);
      clearInterval(statusInterval);
    };
  }, []);

  const circumference = 2 * Math.PI * 45;
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  if (error) {
    return (
      <div className="init-screen">
        <div className="error-icon">⚠️</div>
        <p className="init-status error">{error}</p>
        <button
          className="retry-btn"
          onClick={() => window.location.reload()}
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="init-screen">
      <div className="progress-container">
        <svg className="progress-ring" width="120" height="120">
          <circle
            className="progress-ring-bg"
            cx="60"
            cy="60"
            r="45"
            fill="none"
            strokeWidth="8"
          />
          <circle
            className="progress-ring-fill"
            cx="60"
            cy="60"
            r="45"
            fill="none"
            strokeWidth="8"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
          />
        </svg>
        <div className="progress-text">{progress}%</div>
      </div>
      <p className="init-status">{statusText}</p>
    </div>
  );
}

export default InitScreen;

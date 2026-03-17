import type { Message } from './MainScreen';

interface MessageItemProps {
  message: Message;
}

function MessageItem({ message }: MessageItemProps) {
  const emotionColors = {
    suspicious: '#ff6b6b',
    trust: '#51cf66',
    neutral: '#adb5bd',
  };

  const emotionLabels = {
    suspicious: '可疑',
    trust: '可信',
    neutral: '中性',
  };

  return (
    <div className="message-item">
      <div className="message-header">
        <span className="message-speaker">
          <span className="speaker-icon">🔊</span>
          {message.speaker}
        </span>
        <span
          className="message-emotion"
          style={{ color: emotionColors[message.emotion] }}
        >
          {emotionLabels[message.emotion]}
        </span>
      </div>
      <div className="message-content">{message.content}</div>
    </div>
  );
}

export default MessageItem;

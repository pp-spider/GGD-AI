interface ToggleButtonProps {
  isListening: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

function ToggleButton({ isListening, onToggle, disabled }: ToggleButtonProps) {
  return (
    <button
      className={`toggle-button ${isListening ? 'listening' : ''} ${disabled ? 'disabled' : ''}`}
      onClick={onToggle}
      disabled={disabled}
    >
      <span className="toggle-icon">{isListening ? '⏹' : '▶'}</span>
      <span className="toggle-text">
        {isListening ? '结束监听' : '开始监听'}
      </span>
    </button>
  );
}

export default ToggleButton;

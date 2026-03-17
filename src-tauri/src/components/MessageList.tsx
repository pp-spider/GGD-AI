import { useRef, useEffect } from 'react';
import MessageItem from './MessageItem';
import type { Message } from './MainScreen';

interface MessageListProps {
  messages: Message[];
}

function MessageList({ messages }: MessageListProps) {
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  let lastRound = 0;

  return (
    <div className="message-list" ref={listRef}>
      {messages.map((message) => {
        const showRoundDivider = message.round !== lastRound;
        lastRound = message.round;

        return (
          <div key={message.id}>
            {showRoundDivider && (
              <div className="round-divider">
                <span className="round-divider-text">[第{message.round}轮]</span>
              </div>
            )}
            <MessageItem message={message} />
          </div>
        );
      })}
    </div>
  );
}

export default MessageList;

import { useState, useEffect } from 'react';
import InitScreen from './components/InitScreen';
import MainScreen from './components/MainScreen';

export type PageState = 'init' | 'main';

const API_BASE_URL = 'http://127.0.0.1:9876/api';

function App() {
  const [pageState, setPageState] = useState<PageState>('init');
  const [initError, setInitError] = useState<string | null>(null);

  useEffect(() => {
    // 初始化系统
    const initSystem = async () => {
      try {
        // 等待后端服务启动
        let retries = 0;
        const maxRetries = 30;

        while (retries < maxRetries) {
          try {
            const response = await fetch(`${API_BASE_URL}/init`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
              const data = await response.json();
              if (data.status === 'success') {
                setPageState('main');
                return;
              }
            }
          } catch (e) {
            // 后端尚未启动，继续等待
          }

          retries++;
          await new Promise(resolve => setTimeout(resolve, 1000));
        }

        setInitError('无法连接到后端服务，请检查Python服务是否已启动');
      } catch (e) {
        setInitError('初始化失败: ' + (e as Error).message);
      }
    };

    initSystem();
  }, []);

  return (
    <div className="app-container">
      {pageState === 'init' && <InitScreen error={initError} />}
      {pageState === 'main' && <MainScreen />}
    </div>
  );
}

export default App;

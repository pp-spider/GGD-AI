import { useState, useEffect } from "react";
import InitScreen from "./components/InitScreen";
import SetupScreen from "./components/SetupScreen";
import MainScreen from "./components/MainScreen";
import { useMonitor } from "./hooks/useMonitor";

function App() {
  const [initialized, setInitialized] = useState(false);
  const [setupComplete, setSetupComplete] = useState(false);
  const { status, initSystem, setMyPlayerId } = useMonitor();

  useEffect(() => {
    // 初始化系统
    initSystem().then(() => {
      setInitialized(true);
      // 检查是否已有保存的玩家ID
      const savedPlayerId = localStorage.getItem("ggd_ai_my_player_id");
      if (savedPlayerId) {
        setMyPlayerId(savedPlayerId);
        setSetupComplete(true);
      }
    });
  }, [initSystem, setMyPlayerId]);

  // 处理设置完成
  const handleSetupComplete = (playerId: string) => {
    setMyPlayerId(playerId);
    setSetupComplete(true);
  };

  // 处理重新设置（修改玩家ID）
  const handleResetSetup = () => {
    localStorage.removeItem("ggd_ai_my_player_id");
    setMyPlayerId("");
    setSetupComplete(false);
  };

  if (!initialized) {
    return <InitScreen status={status} />;
  }

  if (!setupComplete) {
    return <SetupScreen onComplete={handleSetupComplete} />;
  }

  return <MainScreen onResetSetup={handleResetSetup} />;
}

export default App;

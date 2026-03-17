import { useState, useEffect } from "react";
import InitScreen from "./components/InitScreen";
import MainScreen from "./components/MainScreen";
import { useMonitor } from "./hooks/useMonitor";

function App() {
  const [initialized, setInitialized] = useState(false);
  const { status, initSystem } = useMonitor();

  useEffect(() => {
    // 初始化系统
    initSystem().then(() => {
      setInitialized(true);
    });
  }, []);

  if (!initialized) {
    return <InitScreen status={status} />;
  }

  return <MainScreen />;
}

export default App;

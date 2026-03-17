// 重新导出 MonitorContext 中的 hook 和类型
// 这是为了保持向后兼容性，实际实现已移至 MonitorContext
export { useMonitor, MonitorProvider } from "../contexts/MonitorContext";
export type { Record, MonitorContextValue } from "../contexts/MonitorContext";

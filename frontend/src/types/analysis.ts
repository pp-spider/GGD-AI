/**
 * AI分析相关类型定义
 */

/** 身份推测类型 */
export type IdentityGuess = "goose" | "duck" | "neutral" | "unknown";

/** 关系类型 */
export type RelationType = "ally" | "enemy" | "neutral" | "suspicious";

/** 玩家分析数据 */
export interface PlayerAnalysis {
  playerId: string;
  playerName: string;
  identityGuess: IdentityGuess;
  confidence: number; // 0-1
  reasoning: string;
  suspiciousPoints: string[];
  trustworthyPoints: string[];
}

/** 玩家关系 */
export interface Relationship {
  from: string;
  to: string;
  type: RelationType;
  evidence: string;
}

/** AI分析结果 */
export interface AIAnalysisResult {
  round: number;
  timestamp: string;
  playerAnalysis: PlayerAnalysis[];
  relationshipMap: Relationship[];
  summary: string;
}

/** 分析状态 */
export interface AnalysisStatus {
  isAnalyzing: boolean;
  currentRound: number;
  lastResult?: AIAnalysisResult;
}

/** WebSocket AI分析消息 */
export interface AIAnalysisStartedMessage {
  type: "ai_analysis_started";
  data: {
    round: number;
    timestamp: string;
  };
}

export interface AIAnalysisCompletedMessage {
  type: "ai_analysis_completed";
  data: {
    round: number;
    status: "success" | "empty" | "error";
    analysis?: AIAnalysisResult;
    message?: string;
  };
}

export interface AIAnalysisErrorMessage {
  type: "ai_analysis_error";
  data: {
    round: number;
    status: "error";
    message: string;
  };
}

export type AIAnalysisMessage =
  | AIAnalysisStartedMessage
  | AIAnalysisCompletedMessage
  | AIAnalysisErrorMessage;

/** 身份标签配置 */
export const IDENTITY_LABELS: Record<IdentityGuess, { label: string; color: string; icon: string }> = {
  goose: { label: "鹅", color: "#4CAF50", icon: "🦢" },
  duck: { label: "鸭子", color: "#F44336", icon: "🦆" },
  neutral: { label: "中立", color: "#9E9E9E", icon: "⚖️" },
  unknown: { label: "未知", color: "#757575", icon: "❓" },
};

/** 关系标签配置 */
export const RELATION_LABELS: Record<RelationType, { label: string; color: string; icon: string }> = {
  ally: { label: "同盟", color: "#4CAF50", icon: "🤝" },
  enemy: { label: "敌对", color: "#F44336", icon: "⚔️" },
  suspicious: { label: "可疑", color: "#FF9800", icon: "👁️" },
  neutral: { label: "中立", color: "#9E9E9E", icon: "⚪" },
};

/** 置信度颜色 */
export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "#4CAF50";
  if (confidence >= 0.6) return "#8BC34A";
  if (confidence >= 0.4) return "#FFC107";
  if (confidence >= 0.2) return "#FF9800";
  return "#9E9E9E";
}

/** 置信度标签 */
export function getConfidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "高";
  if (confidence >= 0.6) return "较高";
  if (confidence >= 0.4) return "中等";
  if (confidence >= 0.2) return "较低";
  return "未知";
}

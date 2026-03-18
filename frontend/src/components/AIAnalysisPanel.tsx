/**
 * AI分析面板组件
 * 展示AI对玩家身份和关系的分析结果
 */

import React, { useState } from "react";
import { useMonitor } from "../contexts/MonitorContext";
import {
  IDENTITY_LABELS,
  RELATION_LABELS,
  getConfidenceColor,
  getConfidenceLabel,
  type IdentityGuess,
  type RelationType,
  type PlayerAnalysis,
  type Relationship,
} from "../types/analysis";
import "../styles/ai-analysis.css";

export function AIAnalysisPanel() {
  const { analysisResult, isAnalyzing, currentRound } = useMonitor();
  const [expandedPlayer, setExpandedPlayer] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"players" | "relations">("players");

  // 如果正在分析中，显示加载状态
  if (isAnalyzing) {
    return (
      <div className="ai-analysis-panel acrylic">
        <div className="ai-analysis-header">
          <h3>
            <span className="ai-icon">🤖</span>
            AI分析助手
          </h3>
        </div>
        <div className="ai-analysis-loading">
          <div className="loading-spinner"></div>
          <p>AI正在分析第{currentRound}轮发言...</p>
          <span className="loading-subtitle">请稍候，正在推理玩家身份关系</span>
        </div>
      </div>
    );
  }

  // 如果没有分析结果
  if (!analysisResult) {
    return (
      <div className="ai-analysis-panel acrylic">
        <div className="ai-analysis-header">
          <h3>
            <span className="ai-icon">🤖</span>
            AI分析助手
          </h3>
        </div>
        <div className="ai-analysis-empty">
          <span className="empty-icon">📊</span>
          <p>暂无AI分析结果</p>
          <span className="empty-subtitle">
            停止监听后将自动生成分析报告
          </span>
        </div>
      </div>
    );
  }

  const { playerAnalysis, relationshipMap, summary, round } = analysisResult;

  return (
    <div className="ai-analysis-panel acrylic">
      <div className="ai-analysis-header">
        <h3>
          <span className="ai-icon">🤖</span>
          AI分析助手
        </h3>
        <span className="analysis-round">第{round}轮</span>
      </div>

      {/* 总结 */}
      <div className="ai-analysis-summary">
        <p>{summary}</p>
        <span className="disclaimer">*AI推测仅供参考</span>
      </div>

      {/* 标签切换 */}
      <div className="ai-analysis-tabs">
        <button
          className={`tab-btn ${activeTab === "players" ? "active" : ""}`}
          onClick={() => setActiveTab("players")}
        >
          身份分析
        </button>
        <button
          className={`tab-btn ${activeTab === "relations" ? "active" : ""}`}
          onClick={() => setActiveTab("relations")}
        >
          关系图谱
        </button>
      </div>

      {/* 玩家身份分析 */}
      {activeTab === "players" && (
        <div className="ai-analysis-content">
          <div className="player-analysis-list">
            {playerAnalysis.map((player) => (
              <PlayerAnalysisCard
                key={player.playerId}
                player={player}
                isExpanded={expandedPlayer === player.playerId}
                onToggle={() =>
                  setExpandedPlayer(
                    expandedPlayer === player.playerId ? null : player.playerId
                  )
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* 关系图谱 */}
      {activeTab === "relations" && (
        <div className="ai-analysis-content">
          {relationshipMap.length > 0 ? (
            <div className="relationship-list">
              {relationshipMap.map((rel, index) => (
                <RelationshipCard key={index} relationship={rel} />
              ))}
            </div>
          ) : (
            <div className="empty-relations">
              <span>暂无足够数据推断关系</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/** 玩家分析卡片 */
function PlayerAnalysisCard({
  player,
  isExpanded,
  onToggle,
}: {
  player: PlayerAnalysis;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const identity = IDENTITY_LABELS[player.identityGuess as IdentityGuess];
  const confidenceColor = getConfidenceColor(player.confidence);

  return (
    <div
      className={`player-analysis-card ${isExpanded ? "expanded" : ""}`}
      onClick={onToggle}
    >
      <div className="player-card-header">
        <div className="player-info">
          <span className="player-id">{player.playerId}</span>
          <span className="player-name">{player.playerName}</span>
        </div>
        <div className="identity-badge" style={{ backgroundColor: identity.color }}>
          <span className="identity-icon">{identity.icon}</span>
          <span className="identity-label">{identity.label}</span>
        </div>
      </div>

      <div className="confidence-bar">
        <div
          className="confidence-fill"
          style={{
            width: `${player.confidence * 100}%`,
            backgroundColor: confidenceColor,
          }}
        />
        <span className="confidence-text">
          置信度: {getConfidenceLabel(player.confidence)}
        </span>
      </div>

      {isExpanded && (
        <div className="player-card-details">
          <div className="detail-section">
            <h4>📝 推理说明</h4>
            <p>{player.reasoning}</p>
          </div>

          {player.trustworthyPoints.length > 0 && (
            <div className="detail-section">
              <h4>✅ 可信点</h4>
              <ul>
                {player.trustworthyPoints.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            </div>
          )}

          {player.suspiciousPoints.length > 0 && (
            <div className="detail-section">
              <h4>⚠️ 可疑点</h4>
              <ul>
                {player.suspiciousPoints.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {!isExpanded && (
        <div className="expand-hint">点击查看详情</div>
      )}
    </div>
  );
}

/** 关系卡片 */
function RelationshipCard({ relationship }: { relationship: Relationship }) {
  const relation = RELATION_LABELS[relationship.type as RelationType];

  return (
    <div className="relationship-card">
      <div className="relationship-players">
        <span className="player-tag">{relationship.from}</span>
        <span className="relation-arrow" style={{ color: relation.color }}>
          {relation.icon} →
        </span>
        <span className="player-tag">{relationship.to}</span>
        <span
          className="relation-badge"
          style={{ backgroundColor: relation.color }}
        >
          {relation.label}
        </span>
      </div>
      <p className="relationship-evidence">{relationship.evidence}</p>
    </div>
  );
}

export default AIAnalysisPanel;

export interface Record {
  timestamp: string;
  text: string;
  speaker: string;
  emotion: 'suspicious' | 'trust' | 'neutral';
  round: number;
}

export interface SpeakerChangeEvent {
  from: string;
  to: string;
}

export interface StatusEvent {
  monitoring: boolean;
  current_speaker?: string;
  current_round?: number;
}

export interface WebSocketMessage {
  type: 'record' | 'speaker_change' | 'status' | 'error' | 'ping' | 'pong';
  data: any;
}

export interface StartMonitorRequest {
  window_title?: string;
  player_count?: number;
}

export interface StartMonitorResponse {
  success: boolean;
  message?: string;
}

export interface StopMonitorResponse {
  success: boolean;
  message?: string;
}

export interface Player {
  number: number;
  name: string;
}

export interface GameState {
  round: number;
  currentSpeaker: string | null;
  players: Player[];
  isMonitoring: boolean;
}

export type EmotionType = 'suspicious' | 'trust' | 'neutral';

export interface AnalysisResult {
  speaker: string;
  emotion: EmotionType;
  confidence: number;
  keywords: string[];
}

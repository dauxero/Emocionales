/**
 * Modelos TypeScript alineados con la API del Diario Emocional v2.0
 */

// ── Request ──
export interface AnalyzeRequest {
  text: string;
  student_age_range?: string | null;
  context?: string | null;
}

// ── Response ──
export interface EmotionDetail {
  label_en: string;
  label_es: string;
  emoji: string;
  category: string;
  score: number;
}

export interface IntensityDetail {
  level: string;
  emoji: string;
  value: number;
}

export interface RiskDetail {
  label: string;
  score: number;
  is_school_related: boolean;
}

export interface RouteDetail {
  name: string;
  requires_follow_up: boolean;
}

export interface AnalysisResponse {
  text: string;
  timestamp: string;
  context: string | null;
  student_age_range: string | null;

  dominant_emotion: EmotionDetail;
  intensity: IntensityDetail;
  all_emotions: EmotionDetail[];

  risk_analysis: RiskDetail[];

  alert_level: string;
  alert_emoji: string;
  alert_description: string;
  route: RouteDetail;
  recommendations: string[];

  positive_reinforcement: string[];
}

// ── Opciones de UI ──
export interface SelectOption {
  value: string;
  label: string;
}

export const AGE_RANGES: SelectOption[] = [
  { value: '6-9', label: '6 – 9 años' },
  { value: '10-13', label: '10 – 13 años' },
  { value: '14-17', label: '14 – 17 años' },
];

export const CONTEXT_OPTIONS: SelectOption[] = [
  { value: 'diario', label: '📓 Diario' },
  { value: 'check-in', label: '✅ Check-in' },
  { value: 'actividad', label: '🎯 Actividad' },
];

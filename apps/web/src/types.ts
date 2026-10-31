export interface SessionResponse {
  csrf: string;
  expires_at: string;
  retention_hours: number;
}

export interface VideoMetadata {
  duration_ms: number;
  width: number;
  height: number;
  audio_present: boolean;
  bytes: number;
  caveats: string[];
  codec?: string;
  original_key?: string;
  storage_ready?: boolean;
}

export interface VideoItem {
  id: string;
  metadata: VideoMetadata;
  created_at: string;
  run_id?: string | null;
}

export interface AnalysisResponse {
  video_id: string;
  metadata: VideoMetadata;
  features: {
    scenes: Array<{ scene_id: number; start_ms: number; end_ms: number }>;
    caveats?: string[];
  };
  available_profiles: ('flash' | 'test')[];
}

export interface RunManifest {
  schema_version: string;
  profile: 'flash' | 'test';
  provider_mode: string;
  requested: number;
  persona_ids: string[];
  resample_seed: number;
}

export interface RunState {
  run_id: string;
  video_id: string;
  status: 'queued' | 'processing' | 'simulating' | 'complete' | 'incomplete' | 'failed';
  stage: 'queued' | 'decoding' | 'simulating' | 'reporting' | 'report' | 'failed';
  error_code?: string | null;
  sequence: number;
  requested: number;
  effective: number;
  failed: number;
  pending: number;
  stopped?: number;
  manifest?: RunManifest;
}

export interface QuoteItem {
  evidence_id: string;
  text: string;
}

export interface NoteItem {
  id: string;
  start_ms: number;
  end_ms: number;
  trigger_id: string;
  interpretation: string;
  fix: string;
  evidence_refs: string[];
  quotes: QuoteItem[];
  status: string;
  ranking_method: string;
}

export interface ObservationItem {
  id: string;
  scene_id: number;
  start_ms: number;
  end_ms: number;
  kind: string;
  numerator: number;
  denominator: number;
  value: number;
  threshold: number;
  evidence_refs: string[];
}

export interface EvidenceItem {
  id: string;
  persona_id: string;
  scene_id: number;
  start_ms: number;
  end_ms: number;
  quote?: string;
  text?: string;
  kind: string;
  still_watching: boolean;
  actions?: Array<{ type: string; at_ms?: number | null } | string>;
  reason?: string;
}

export interface MetricItem {
  kind: 'observed_count' | 'simulation_range' | 'heuristic_index' | 'hypothetical_reach' | string;
  unit: string;
  observed?: number | null;
  denominator?: number | null;
  range?: {
    low: number;
    high: number;
    method: string;
  } | null;
  evidence_ids: string[];
  unavailable_reason?: string | null;
}

export interface RetentionRow {
  scene_id: number;
  start_ms: number;
  end_ms: number;
  entrants: number;
  stopped: number;
  continued: number;
  survival: MetricItem;
  drop_rate: MetricItem;
}

export interface EngagementMetrics {
  like: MetricItem;
  share: MetricItem;
  save: MetricItem;
  comment: MetricItem;
  follow: MetricItem;
  [key: string]: MetricItem;
}

export interface ScoreMetrics {
  hook: MetricItem;
  pacing: MetricItem;
  clarity: MetricItem;
  cta: MetricItem;
  trend: MetricItem;
  [key: string]: MetricItem;
}

export interface NoteRejections {
  unsupported_trigger: number;
  quote_mismatch: number;
  invalid_time: number;
  invalid_reference: number;
  malformed_candidate: number;
}

export interface TrustManifest {
  mode: string;
  label?: string;
  source_sha: string;
  source_observed_at?: string;
  media_sha256: string;
  model_ids: string[];
  reported_versions: (string | null)[];
  training_cutoff: string;
  live_calls?: number;
  limitations: string[];
  app_source_sha: string;
  observed_at: string;
  feature_sha256?: string;
  cast_sha256?: string;
  config_sha256?: string;
  prompt_sha256?: string;
  usage_ledger?: any[];
}

export interface ReportData {
  schema_version: string;
  manifest?: RunManifest;
  duration_ms?: number;
  scenes?: { scene_id: number; start_ms: number; end_ms: number }[];
  suppressed_notes?: number;
  note_rejections?: NoteRejections;
  cast: {
    profile: string;
    requested: number;
    effective: number;
    failed: number;
    pending: number;
    stopped: number;
    status: string;
  };
  retention?: RetentionRow[];
  engagement?: EngagementMetrics;
  scores?: ScoreMetrics;
  notes: NoteItem[];
  observations: ObservationItem[];
  evidence: EvidenceItem[];
  completion: MetricItem;
  trust: TrustManifest;
  methodology: {
    range_kind: string;
    ranking: string;
    assumptions: string[];
  };
  caveats: string[];
  coverage?: {
    transcript: boolean;
    ocr: boolean;
    confused: boolean | null;
    cta_understood: boolean | null;
    trend_fit: boolean | null;
    excluded_traces?: {
      failed: string[];
      pending: string[];
    };
  };
}

export interface DeletionTarget {
  status: 'pending' | 'failed' | 'complete';
  attempts: number;
  completed_at?: string | null;
  retry_at?: string | null;
  error_code?: string | null;
}

export interface DeletionState {
  deletion_id: string;
  repeat_deletion_id: string;
  access_revoked: boolean;
  access_revoked_at: string;
  fence_generation: number;
  targets: Record<string, DeletionTarget>;
  pending_targets: string[];
  can_claim_complete: boolean;
  status: 'pending' | 'complete';
  completed_at?: string | null;
  caveat: string;
}

export interface SimulationEvent {
  event_id: string;
  sequence: number;
  type: string;
  payload: {
    persona_id: string;
    scene_id: number;
    at_ms?: number;
    evidence_id?: string;
    drop_reason?: string;
    actions?: Array<{ type: string; at_ms?: number | null } | string>;
    reason?: string;
    through_sequence?: number;
    reset?: boolean;
  };
  created_at?: string;
}

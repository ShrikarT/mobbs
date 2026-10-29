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

export interface RunState {
  run_id: string;
  video_id: string;
  status: 'queued' | 'processing' | 'complete' | 'failed';
  stage: 'queued' | 'decoding' | 'simulating' | 'reporting' | 'report' | 'failed';
  error_code?: string | null;
  sequence: number;
  requested: number;
  effective: number;
  failed: number;
  pending: number;
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
  quote: string;
  kind: string;
  still_watching: boolean;
}

export interface CompletionMetric {
  kind: string;
  unit: string;
  observed?: number | null;
  denominator: number;
  range?: {
    low: number;
    high: number;
    method: string;
  } | null;
  evidence_ids: string[];
}

export interface TrustManifest {
  mode: string;
  label: string;
  source_sha: string;
  source_observed_at: string;
  media_sha256: string;
  model_ids: string[];
  reported_versions: (string | null)[];
  training_cutoff: string;
  live_calls: number;
  limitations: string[];
  app_source_sha: string;
  observed_at: string;
  usage_ledger?: any[];
}

export interface ReportData {
  schema_version: string;
  cast: {
    profile: string;
    requested: number;
    effective: number;
    failed: number;
    pending: number;
    stopped: number;
    status: string;
  };
  notes: NoteItem[];
  observations: ObservationItem[];
  evidence: EvidenceItem[];
  completion: CompletionMetric;
  trust: TrustManifest;
  methodology: {
    range_kind: string;
    ranking: string;
    assumptions: string[];
  };
  caveats: string[];
  coverage: {
    transcript: boolean;
    ocr: boolean;
    confused: boolean | null;
    cta_understood: boolean | null;
    trend_fit: boolean | null;
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

import {
  SessionResponse,
  RunState,
  ReportData,
  DeletionState,
  VideoItem,
  AnalysisResponse,
  EvidenceItem,
} from './types';

export function makeIdempotencyKey(prefix = 'idem'): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let rand = '';
  for (let i = 0; i < 16; i++) {
    rand += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return `${prefix}_${Date.now()}_${rand}`;
}

export async function ensureSession(): Promise<SessionResponse> {
  const res = await fetch('/sessions', {
    method: 'POST',
    headers: {
      'Accept': 'application/json',
    },
  });
  if (!res.ok) {
    const err: any = new Error(`Failed to initialize session: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function listVideos(): Promise<VideoItem[]> {
  const res = await fetch('/videos', {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    const err: any = new Error(`Failed to list videos: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function uploadVideo(
  blob: Blob,
  csrf: string,
  key = makeIdempotencyKey('up')
): Promise<{ video_id: string; status: string }> {
  const res = await fetch('/videos', {
    method: 'POST',
    headers: {
      'Content-Type': 'video/mp4',
      'X-CSRF-Token': csrf,
      'Idempotency-Key': key,
    },
    body: blob,
  });
  if (!res.ok) {
    const errObj = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    const err: any = new Error(errObj.code || errObj.message || `Upload failed: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchAnalysis(videoId: string): Promise<AnalysisResponse> {
  const res = await fetch(`/videos/${videoId}/analysis`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    const errObj = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    const err: any = new Error(errObj.code || errObj.message || `Failed to fetch analysis: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function startRun(
  videoId: string,
  csrf: string,
  profile: 'flash' | 'test' = 'flash',
  key = makeIdempotencyKey('run')
): Promise<{ run_id: string; status: string }> {
  const res = await fetch('/runs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
      'Idempotency-Key': key,
    },
    body: JSON.stringify({ video_id: videoId, profile }),
  });
  if (!res.ok) {
    const errObj = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    const err: any = new Error(errObj.code || errObj.message || `Run creation failed: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchRun(runId: string): Promise<RunState> {
  const res = await fetch(`/runs/${runId}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    const err: any = new Error(`Failed to fetch run: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchEvidence(runId: string, evidenceId: string): Promise<EvidenceItem> {
  const res = await fetch(`/runs/${runId}/evidence/${evidenceId}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    const err: any = new Error(`Failed to fetch evidence: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchReport(runId: string): Promise<{ ready: boolean; report?: ReportData; stage?: string }> {
  const res = await fetch(`/runs/${runId}/report`, {
    headers: { 'Accept': 'application/json' },
  });
  if (res.status === 202) {
    const body = await res.json();
    return { ready: false, stage: body.stage };
  }
  if (!res.ok) {
    const err: any = new Error(`Report fetch failed: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  const report = await res.json();
  return { ready: true, report };
}

export async function requestDelete(
  videoId: string,
  csrf: string,
  key = makeIdempotencyKey('del')
): Promise<DeletionState> {
  const res = await fetch(`/videos/${videoId}`, {
    method: 'DELETE',
    headers: {
      'X-CSRF-Token': csrf,
      'Idempotency-Key': key,
    },
  });
  if (!res.ok) {
    const errObj = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    const err: any = new Error(errObj.code || errObj.message || `Deletion failed: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function fetchDeletion(deletionId: string): Promise<DeletionState> {
  const res = await fetch(`/deletions/${deletionId}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    const err: any = new Error(`Failed to fetch deletion status: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export async function listDeletions(): Promise<{ id: string; video_id: string; state: DeletionState }[]> {
  const res = await fetch('/deletions', {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) {
    const err: any = new Error(`Failed to list deletions: HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

import { SessionResponse, RunState, ReportData, DeletionState, VideoItem } from './types';

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
    throw new Error(`Failed to initialize session: HTTP ${res.status}`);
  }
  return res.json();
}

export async function listVideos(): Promise<VideoItem[]> {
  const res = await fetch('/videos', {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to list videos: HTTP ${res.status}`);
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
    const err = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    throw new Error(err.code || err.message || `Upload failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function startRun(
  videoId: string,
  csrf: string,
  key = makeIdempotencyKey('run')
): Promise<{ run_id: string; status: string }> {
  const res = await fetch('/runs', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-Token': csrf,
      'Idempotency-Key': key,
    },
    body: JSON.stringify({ video_id: videoId, profile: 'test' }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    throw new Error(err.code || err.message || `Run creation failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchRun(runId: string): Promise<RunState> {
  const res = await fetch(`/runs/${runId}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to fetch run: HTTP ${res.status}`);
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
    throw new Error(`Report fetch failed: HTTP ${res.status}`);
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
    const err = await res.json().catch(() => ({ code: `HTTP_${res.status}` }));
    throw new Error(err.code || err.message || `Deletion failed: HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchDeletion(deletionId: string): Promise<DeletionState> {
  const res = await fetch(`/deletions/${deletionId}`, {
    headers: { 'Accept': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to fetch deletion status: HTTP ${res.status}`);
  return res.json();
}

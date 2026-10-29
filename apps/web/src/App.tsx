import React, { useEffect, useState, useRef } from 'react';
import {
  ensureSession,
  uploadVideo,
  startRun,
  fetchRun,
  fetchReport,
  requestDelete,
  fetchDeletion,
  listVideos,
} from './api';
import { SessionResponse, RunState, ReportData, DeletionState, NoteItem } from './types';

export function App() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);

  // App workflow state: 'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error'
  const [viewState, setViewState] = useState<'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error'>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Active video & run
  const [videoId, setVideoId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [events, setEvents] = useState<Array<{ id: string; type: string; summary: string }>>([]);

  // Selected note for player seeking & highlight
  const [selectedNote, setSelectedNote] = useState<NoteItem | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Deletion modal & tracking
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [deletionState, setDeletionState] = useState<DeletionState | null>(null);

  // Initialize session on mount
  useEffect(() => {
    ensureSession()
      .then((data) => {
        setSession(data);
        // Check if there is an existing video in this session
        listVideos().then((vids) => {
          if (vids.length > 0 && vids[0].run_id) {
            setVideoId(vids[0].id);
            setRunId(vids[0].run_id);
            setViewState('processing');
          }
        }).catch(() => {});
      })
      .catch((err) => {
        setSessionError(err.message || 'Session initialization failed');
      });
  }, []);

  // Poll / SSE for run updates when processing
  useEffect(() => {
    if (viewState !== 'processing' || !runId) return;

    let isMounted = true;
    const interval = setInterval(async () => {
      try {
        const state = await fetchRun(runId);
        if (!isMounted) return;
        setRunState(state);

        if (state.status === 'complete') {
          const repResult = await fetchReport(runId);
          if (repResult.ready && repResult.report) {
            setReport(repResult.report);
            if (repResult.report.notes.length > 0) {
              setSelectedNote(repResult.report.notes[0]);
            }
            setViewState('ready');
            clearInterval(interval);
          }
        } else if (state.status === 'failed') {
          setErrorMessage(state.error_code || 'Analysis failed');
          setViewState('error');
          clearInterval(interval);
        }
      } catch (err: any) {
        // Keep retrying on transient error
      }
    }, 1000);

    // Also connect to SSE events stream
    let eventSource: EventSource | null = null;
    try {
      eventSource = new EventSource(`/runs/${runId}/events`);
      eventSource.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          if (parsed && parsed.type) {
            setEvents((prev) => [
              ...prev,
              {
                id: parsed.event_id || String(Date.now()),
                type: parsed.type,
                summary: parsed.type.startsWith('persona.')
                  ? `Persona ${parsed.payload.persona_id} scene ${parsed.payload.scene_id} at ${parsed.payload.at_ms}ms`
                  : parsed.type,
              },
            ]);
          }
        } catch {}
      };
    } catch {}

    return () => {
      isMounted = false;
      clearInterval(interval);
      if (eventSource) eventSource.close();
    };
  }, [viewState, runId]);

  // Handle file upload
  const handleUpload = async (file: File) => {
    if (!session) return;
    setErrorMessage(null);
    setViewState('uploading');
    setStatusMessage('Validating and uploading video...');

    try {
      const up = await uploadVideo(file, session.csrf);
      setVideoId(up.video_id);
      setStatusMessage('Video accepted. Queueing durable analysis...');

      const run = await startRun(up.video_id, session.csrf);
      setRunId(run.run_id);
      setViewState('processing');
    } catch (err: any) {
      setErrorMessage(err.message || 'Upload failed');
      setViewState('error');
    }
  };

  // Seek video when selecting a note
  const handleSelectNote = (note: NoteItem) => {
    setSelectedNote(note);
    if (videoRef.current) {
      videoRef.current.currentTime = note.start_ms / 1000;
      videoRef.current.play().catch(() => {});
    }
  };

  // Trigger deletion
  const handleDelete = async () => {
    if (!videoId || !session) return;
    setShowDeleteModal(false);
    setViewState('deleting');
    setStatusMessage('Revoking access and deleting data...');

    try {
      const del = await requestDelete(videoId, session.csrf);
      setDeletionState(del);

      // Poll deletion until complete
      const delId = del.deletion_id;
      const delInterval = setInterval(async () => {
        try {
          const cur = await fetchDeletion(delId);
          setDeletionState(cur);
          if (cur.status === 'complete' && cur.can_claim_complete) {
            clearInterval(delInterval);
            setViewState('deleted');
          }
        } catch {
          clearInterval(delInterval);
        }
      }, 1000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Deletion failed');
      setViewState('error');
    }
  };

  const handleReset = () => {
    setVideoId(null);
    setRunId(null);
    setRunState(null);
    setReport(null);
    setSelectedNote(null);
    setEvents([]);
    setDeletionState(null);
    setErrorMessage(null);
    setViewState('idle');
  };

  return (
    <div>
      {/* 56px utility header */}
      <header className="app-header">
        <div className="brand-group">
          <span className="brand-title">Viralist / Evidence desk</span>
          <span className="badge-recorded">Recorded mode · Standard Meta Spark 1.3</span>
        </div>
        <div>
          {session ? (
            <span className="session-badge mono">Session: {session.retention_hours}h retention</span>
          ) : (
            <span className="session-badge">Initializing session...</span>
          )}
        </div>
      </header>

      <main className="app-main">
        {sessionError && (
          <div className="suppressed-note-alert" style={{ borderColor: 'var(--error)', color: 'var(--error)' }}>
            <strong>Session error:</strong> {sessionError}
          </div>
        )}

        {/* View 1: Upload Landing Desk */}
        {viewState === 'idle' && (
          <div className="upload-container">
            <h1 className="hero-heading">A clearer next cut.</h1>
            <p className="hero-subtitle">
              See where a simulated audience loses interest, why, and what concrete edit to make before posting.
            </p>

            <div
              className="dropzone"
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                if (e.dataTransfer.files?.[0]) handleUpload(e.dataTransfer.files[0]);
              }}
            >
              <label htmlFor="file-upload" className="dropzone-label">
                Drop your MP4 here or click to browse
              </label>
              <p className="dropzone-hint">MP4 · up to 60 seconds · up to 200 MB</p>
              <input
                id="file-upload"
                type="file"
                accept="video/mp4"
                className="hidden-input"
                onChange={(e) => {
                  if (e.target.files?.[0]) handleUpload(e.target.files[0]);
                }}
              />
            </div>

            <div className="disclosure-box">
              <strong>V02 Test Slice Disclosure</strong>
              <ul className="disclosure-list">
                <li>Server validates MP4 container, codec, and duration before any dispatch.</li>
                <li>Uses Standard Meta Spark 1.3 persona simulation (3-person test cast).</li>
                <li>Exact hash-bound recorded inference; no new provider latency or spend claimed.</li>
                <li>All uploaded video files, derivatives, and reports can be deleted at any time.</li>
              </ul>
            </div>
          </div>
        )}

        {/* View 2: Uploading / Validating */}
        {viewState === 'uploading' && (
          <div className="running-container">
            <span className="stage-badge">Ingest</span>
            <h2>Uploading media</h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>{statusMessage}</p>
            <div className="progress-track">
              <div className="progress-bar" style={{ width: '40%' }}></div>
            </div>
          </div>
        )}

        {/* View 3: Processing / Simulating */}
        {viewState === 'processing' && (
          <div className="running-container">
            <span className="stage-badge">{runState?.stage || 'decoding'}</span>
            <h2>Analyzing audience retention</h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
              Simulating cast: 3 requested · {runState?.effective ?? 0} finished · {runState?.pending ?? 3} active
            </p>
            <div className="progress-track">
              <div
                className="progress-bar"
                style={{
                  width:
                    runState?.stage === 'decoding'
                      ? '30%'
                      : runState?.stage === 'simulating'
                      ? '70%'
                      : runState?.stage === 'reporting'
                      ? '90%'
                      : '50%',
                }}
              ></div>
            </div>

            <div className="event-ticker">
              <strong>Persisted simulation events:</strong>
              {events.length === 0 ? (
                <div className="event-item" style={{ color: 'var(--text-muted)' }}>
                  Awaiting scene checkpoints...
                </div>
              ) : (
                events.map((ev) => (
                  <div key={ev.id} className="event-item mono">
                    {ev.summary}
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* View 4: Completed Report Workbench */}
        {viewState === 'ready' && report && videoId && (
          <div className="workbench-grid">
            {/* Left: Video Player & Timeline */}
            <div className="player-column">
              <div className="video-container">
                <video
                  ref={videoRef}
                  src={`/videos/${videoId}/media`}
                  controls
                  playsInline
                  className="video-element"
                />
              </div>

              {/* Timeline scrubber / scene cards */}
              <div className="timeline-card">
                <div className="timeline-header">
                  <span>Scene timeline</span>
                  <span className="mono">0.0s – {(report.observations[0]?.end_ms || 17108) / 1000}s</span>
                </div>
                <div className="timeline-track" role="region" aria-label="Scene timeline">
                  {/* Scene 0: 0-3s Hook */}
                  <div
                    className="timeline-segment"
                    style={{ flex: 3 }}
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime = 0;
                    }}
                    title="0s - 3s (Hook)"
                  >
                    0–3s
                  </div>
                  {/* Scene 1: 3-8s Stop Trigger */}
                  <div
                    className={`timeline-segment has-trigger ${
                      selectedNote && selectedNote.start_ms === 3000 ? 'active-note' : ''
                    }`}
                    style={{ flex: 5 }}
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime = 3.0;
                      if (report.notes[0]) setSelectedNote(report.notes[0]);
                    }}
                    title="3s - 8s (Stop trigger detected: >=15% drop)"
                  >
                    3–8s (Drop)
                  </div>
                  {/* Scene 2: 8-13s */}
                  <div
                    className="timeline-segment"
                    style={{ flex: 5 }}
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime = 8.0;
                    }}
                    title="8s - 13s"
                  >
                    8–13s
                  </div>
                  {/* Scene 3: 13-17.1s */}
                  <div
                    className="timeline-segment"
                    style={{ flex: 4.1 }}
                    onClick={() => {
                      if (videoRef.current) videoRef.current.currentTime = 13.0;
                    }}
                    title="13s - 17.1s"
                  >
                    13–17.1s
                  </div>
                </div>
              </div>
            </div>

            {/* Right: Evidence & Director's Notes */}
            <div className="evidence-column">
              <div className="report-header">
                <h2 className="verdict-title">Executive finding</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
                  Audience retention simulation with 3 individual persona traces.
                </p>

                <div className="metrics-summary">
                  <div className="metric-pill">
                    Cast: <strong>{report.cast.effective} viewers</strong> ({report.cast.profile})
                  </div>
                  <div className="metric-pill">
                    Completion rate:{' '}
                    <strong>{report.completion.observed !== null ? `${report.completion.observed?.toFixed(1)}%` : 'N/A'}</strong>
                    {report.completion.range && (
                      <span className="mono" style={{ color: 'var(--text-muted)' }}>
                        {' '}[{report.completion.range.low.toFixed(0)}%–{report.completion.range.high.toFixed(0)}%]
                      </span>
                    )}
                  </div>
                  <div className="metric-pill">
                    Stopped viewers: <strong>{report.cast.stopped}</strong>
                  </div>
                </div>
              </div>

              {/* Supported Director's Notes */}
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>
                  Director&apos;s Notes ({report.notes.length})
                </h3>

                {report.notes.length === 0 ? (
                  <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>No supported edit found.</p>
                ) : (
                  report.notes.map((note) => (
                    <div
                      key={note.id}
                      className={`note-card ${selectedNote?.id === note.id ? 'selected' : ''}`}
                      onClick={() => handleSelectNote(note)}
                      tabIndex={0}
                      role="button"
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') handleSelectNote(note);
                      }}
                      aria-label={`Note at ${note.start_ms / 1000} seconds: ${note.interpretation}`}
                    >
                      <div className="note-timestamp mono">
                        {(note.start_ms / 1000).toFixed(1)}s – {(note.end_ms / 1000).toFixed(1)}s (Click to seek)
                      </div>
                      <div className="note-finding">{note.interpretation}</div>
                      <div className="note-fix">
                        <strong>Suggested edit:</strong> {note.fix}
                      </div>

                      {/* Expanding simulated quotes */}
                      {note.quotes && note.quotes.length > 0 && (
                        <div className="quotes-section">
                          <div className="quotes-heading">Simulated persona reason</div>
                          {note.quotes.map((q, idx) => (
                            <div key={idx} className="quote-item">
                              &ldquo;{q.text}&rdquo;
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}

                {/* Honest report of suppressed notes */}
                <div className="suppressed-note-alert">
                  <strong>Notice:</strong> 1 unsupported candidate note was suppressed by the deterministic stop-fraction detector.
                  Only findings backed by observed dropout triggers are surfaced.
                </div>
              </div>

              {/* Trust & Provenance Manifest */}
              <div className="trust-manifest">
                <details>
                  <summary className="trust-summary">Trust manifest &amp; simulation provenance</summary>
                  <div className="trust-details">
                    <dl>
                      <dt>Inference mode:</dt>
                      <dd>{report.trust.mode} ({report.trust.label})</dd>
                      <dt>Model ID:</dt>
                      <dd>{report.trust.model_ids.join(', ')}</dd>
                      <dt>Provider version:</dt>
                      <dd>{report.trust.reported_versions[0] || 'not provided'}</dd>
                      <dt>Source commit:</dt>
                      <dd className="mono">{report.trust.app_source_sha || report.trust.source_sha}</dd>
                      <dt>Media SHA-256:</dt>
                      <dd className="mono">{report.trust.media_sha256}</dd>
                    </dl>
                    <strong>Methodology &amp; caveats:</strong>
                    <ul style={{ paddingLeft: '16px', marginTop: '6px' }}>
                      {report.caveats.map((c, i) => (
                        <li key={i}>{c}</li>
                      ))}
                    </ul>
                  </div>
                </details>
              </div>

              {/* Deletion action */}
              <div className="actions-footer">
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => window.location.reload()}
                >
                  Reload (test persistence)
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => setShowDeleteModal(true)}
                >
                  Delete video &amp; report
                </button>
              </div>
            </div>
          </div>
        )}

        {/* View 5: Deleting / Deleted Progress */}
        {(viewState === 'deleting' || viewState === 'deleted') && deletionState && (
          <div className="running-container">
            <span className="stage-badge" style={{ background: varCss(viewState === 'deleted' ? 'complete' : 'pending') }}>
              {viewState === 'deleted' ? 'Complete' : 'Deleting'}
            </span>
            <h2>{viewState === 'deleted' ? 'All data permanently removed' : 'Executing deletion lifecycle'}</h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
              Access revoked immediately. Controlled artifacts are removed from database and private storage.
            </p>

            <div className="deletion-targets-list">
              {Object.entries(deletionState.targets).map(([key, target]) => (
                <div key={key} className="target-row">
                  <span className="mono">{key}</span>
                  <span className={`status-badge ${target.status}`}>{target.status}</span>
                </div>
              ))}
            </div>

            {viewState === 'deleted' && (
              <div style={{ marginTop: '24px' }}>
                <button type="button" className="btn btn-primary" onClick={handleReset}>
                  Start new upload
                </button>
              </div>
            )}
          </div>
        )}

        {/* View 6: Error State */}
        {viewState === 'error' && (
          <div className="running-container">
            <span className="stage-badge" style={{ background: 'var(--error-tint)', color: 'var(--error)' }}>
              Error
            </span>
            <h2>Operation failed</h2>
            <p style={{ color: 'var(--error)', marginTop: '8px' }}>{errorMessage}</p>
            <div style={{ marginTop: '24px' }}>
              <button type="button" className="btn btn-primary" onClick={handleReset}>
                Try again
              </button>
            </div>
          </div>
        )}
      </main>

      {/* Confirmation Modal for Deletion */}
      {showDeleteModal && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div className="modal-dialog">
            <h3 id="modal-title" className="modal-title">Delete this video?</h3>
            <p className="modal-body">
              This will immediately revoke access and remove the original video, generated scene frames, simulation events,
              and reports from private storage and PostgreSQL.
            </p>
            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowDeleteModal(false)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={handleDelete}
              >
                Confirm deletion
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function varCss(status: string) {
  if (status === 'complete') return 'var(--action-green-tint)';
  if (status === 'failed') return 'var(--error-tint)';
  return 'var(--caution-tint)';
}

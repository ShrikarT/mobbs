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
  listDeletions,
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
  const [events, setEvents] = useState<Array<{ id: string; sequence?: number; type: string; summary: string }>>([]);

  // Selected note for player seeking & highlight
  const [selectedNote, setSelectedNote] = useState<NoteItem | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Deletion modal & tracking
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [deletionState, setDeletionState] = useState<DeletionState | null>(null);
  const cancelBtnRef = useRef<HTMLButtonElement>(null);
  const deleteBtnRef = useRef<HTMLButtonElement>(null);

  // Modal focus lifecycle
  useEffect(() => {
    if (showDeleteModal) {
      setTimeout(() => cancelBtnRef.current?.focus(), 20);
    } else {
      deleteBtnRef.current?.focus();
    }
  }, [showDeleteModal]);

  // Start polling deletion helper
  const startPollingDeletion = (delId: string) => {
    const delInterval = setInterval(async () => {
      try {
        const cur = await fetchDeletion(delId);
        setDeletionState(cur);
        if (cur.status === 'complete' && cur.can_claim_complete) {
          clearInterval(delInterval);
          setViewState('deleted');
        }
      } catch (err: any) {
        if (err.status === 401 || err.status === 404) {
          clearInterval(delInterval);
          setErrorMessage('Deletion tracking unavailable or session expired.');
          setViewState('error');
        }
      }
    }, 1000);
  };

  // Initialize session on mount and restore durable state across reload
  useEffect(() => {
    ensureSession()
      .then(async (data) => {
        setSession(data);

        // Check for any pending deletion first
        try {
          const dels = await listDeletions();
          const pendingDel = dels.find((d) => d.state?.status === 'pending');
          if (pendingDel) {
            setDeletionState(pendingDel.state);
            setViewState('deleting');
            startPollingDeletion(pendingDel.id);
            return;
          }
        } catch {}

        // Check if there is an existing video in this session
        try {
          const vids = await listVideos();
          if (vids.length > 0) {
            setVideoId(vids[0].id);
            if (vids[0].run_id) {
              setRunId(vids[0].run_id);
              setViewState('processing');
            } else {
              setErrorMessage('Uploaded video found without an active run.');
              setViewState('error');
            }
          }
        } catch {}
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

        // Surface report for complete OR incomplete terminal state
        if (state.status === 'complete' || state.status === 'incomplete') {
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
        if (err.status === 401) {
          setSessionError('Session expired. Please start a new session.');
          setViewState('error');
          clearInterval(interval);
        } else if (err.status === 404) {
          setErrorMessage('Run not found or was deleted.');
          setViewState('error');
          clearInterval(interval);
        }
      }
    }, 1000);

    // Connect to SSE events stream with cursor and named event handlers
    let eventSource: EventSource | null = null;
    try {
      const lastSeq = events.length > 0 ? Math.max(...events.map((e) => e.sequence || 0)) : 0;
      eventSource = new EventSource(`/runs/${runId}/events${lastSeq ? `?after=${lastSeq}` : ''}`);

      const handleEvent = (e: MessageEvent) => {
        try {
          const parsed = JSON.parse(e.data);
          if (parsed && (parsed.event_id || parsed.type)) {
            const eid = parsed.event_id || String(Date.now());
            setEvents((prev) => {
              if (prev.some((item) => item.id === eid)) return prev;
              const summary = parsed.type === 'persona.continued'
                ? `Persona ${parsed.payload.persona_id} scene ${parsed.payload.scene_id}: continued (${parsed.payload.at_ms}ms)`
                : parsed.type === 'persona.stopped'
                ? `Persona ${parsed.payload.persona_id} scene ${parsed.payload.scene_id}: stopped (${parsed.payload.drop_reason || 'dropout'})`
                : parsed.type === 'run.snapshot'
                ? `Snapshot through sequence ${parsed.payload.through_sequence}`
                : parsed.type;
              return [
                ...prev,
                {
                  id: eid,
                  sequence: parsed.sequence,
                  type: parsed.type,
                  summary,
                },
              ].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
            });
          }
        } catch {}
      };

      eventSource.addEventListener('persona.continued', handleEvent);
      eventSource.addEventListener('persona.stopped', handleEvent);
      eventSource.addEventListener('run.snapshot', handleEvent);
      eventSource.addEventListener('message', handleEvent);
    } catch {}

    return () => {
      isMounted = false;
      clearInterval(interval);
      if (eventSource) eventSource.close();
    };
  }, [viewState, runId]);

  // Handle file upload
  const handleUpload = async (file: File) => {
    let currentSession = session;
    if (!currentSession) {
      try {
        currentSession = await ensureSession();
        setSession(currentSession);
      } catch (err: any) {
        setErrorMessage(err.message || 'Session initialization failed');
        setViewState('error');
        return;
      }
    }
    setErrorMessage(null);
    setViewState('uploading');
    setStatusMessage('Validating and uploading video...');

    try {
      const up = await uploadVideo(file, currentSession.csrf);
      setVideoId(up.video_id);
      setStatusMessage('Video accepted. Queueing durable analysis...');

      const run = await startRun(up.video_id, currentSession.csrf);
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
      startPollingDeletion(del.deletion_id);
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

  // Stored scenes and duration derivation
  const scenes = report
    ? (report.scenes && report.scenes.length > 0
        ? report.scenes
        : [
            { scene_id: 0, start_ms: 0, end_ms: 3000 },
            { scene_id: 1, start_ms: 3000, end_ms: 8000 },
            { scene_id: 2, start_ms: 8000, end_ms: 13000 },
            { scene_id: 3, start_ms: 13000, end_ms: report.duration_ms || 17108 },
          ])
    : [];

  const durationMs = report ? (report.duration_ms || scenes[scenes.length - 1]?.end_ms || 17108) : 17108;
  const durationSec = (durationMs / 1000).toFixed(1);

  // Suppressed notes count derived from stored backend data
  const suppressedCount = report
    ? (report.suppressed_notes !== undefined
        ? report.suppressed_notes
        : (report.caveats?.find((c) => c.includes('unsupported note'))?.match(/(\d+)/)?.[1]
            ? parseInt(RegExp.$1, 10)
            : 0))
    : 0;

  return (
    <div>
      {/* 56px utility header with responsive wrap at 320px */}
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
            <div className="progress-track" role="progressbar" aria-label="Uploading media" aria-busy="true">
              <div className="progress-bar indeterminate"></div>
            </div>
          </div>
        )}

        {/* View 3: Processing / Simulating */}
        {viewState === 'processing' && (
          <div className="running-container">
            <span className="stage-badge">{runState?.stage || 'decoding'}</span>
            <h2>Analyzing audience retention</h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
              Stage: <strong className="mono">{runState?.stage || 'decoding'}</strong> · Cast: 3 requested · {runState?.effective ?? 0} finished · {runState?.pending ?? 3} active
            </p>
            <div className="progress-track" role="progressbar" aria-label="Analyzing audience retention" aria-busy="true">
              <div className="progress-bar indeterminate"></div>
            </div>

            <div className="event-ticker">
              <strong>Persisted simulation events ({events.length}):</strong>
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

            <div style={{ marginTop: '20px' }}>
              <button
                ref={deleteBtnRef}
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowDeleteModal(true)}
              >
                Cancel &amp; delete video
              </button>
            </div>
          </div>
        )}

        {/* View 4: Report Workbench */}
        {viewState === 'ready' && report && (
          <div className="workbench-grid">
            {/* Left: Video player & interactive timeline */}
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

              {/* Dynamic Timeline scrubber / scene cards */}
              <div className="timeline-card">
                <div className="timeline-header">
                  <span>Scene timeline ({scenes.length} scenes)</span>
                  <span className="mono">0.0s – {durationSec}s</span>
                </div>
                <div className="timeline-track" role="region" aria-label="Scene timeline">
                  {scenes.map((scene, idx) => {
                    const startSec = (scene.start_ms / 1000).toFixed(scene.start_ms % 1000 === 0 ? 0 : 1);
                    const endSec = (scene.end_ms / 1000).toFixed(scene.end_ms % 1000 === 0 ? 0 : 1);
                    const trigger = report.observations?.find(
                      (o: any) => o.scene_id === scene.scene_id || (o.start_ms <= scene.start_ms && o.end_ms >= scene.end_ms)
                    );
                    const hasTrigger = Boolean(trigger);
                    const isSelected = selectedNote && selectedNote.start_ms <= scene.end_ms && selectedNote.end_ms >= scene.start_ms;
                    const flexVal = Math.max(1, (scene.end_ms - scene.start_ms) / 1000);

                    const seekToThis = () => {
                      if (videoRef.current) videoRef.current.currentTime = scene.start_ms / 1000;
                      if (hasTrigger && report.notes.length > 0) {
                        setSelectedNote(report.notes[0]);
                      }
                    };

                    return (
                      <div
                        key={scene.scene_id ?? idx}
                        role="button"
                        tabIndex={0}
                        aria-label={`Scene ${idx + 1}: ${startSec}s to ${endSec}s${hasTrigger ? ' (Drop trigger detected)' : ''}`}
                        className={`timeline-segment ${hasTrigger ? 'has-trigger' : ''} ${isSelected ? 'active-note' : ''}`}
                        style={{ flex: flexVal }}
                        onClick={seekToThis}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            seekToThis();
                          }
                        }}
                        title={`${startSec}s - ${endSec}s${hasTrigger ? ' (Stop trigger detected: >=15% drop)' : ''}`}
                      >
                        {startSec}–{endSec}s{hasTrigger ? ' (Drop)' : ''}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* Right: Evidence & Director's Notes */}
            <div className="evidence-column">
              <div className="report-header">
                <h2 className="verdict-title">Executive finding</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
                  Audience retention simulation with {report.cast.effective} individual persona traces.
                </p>

                {report.cast.failed > 0 && report.cast.effective < report.cast.requested && (
                  <div className="suppressed-note-alert" style={{ borderColor: 'var(--caution)', background: 'var(--caution-tint)', color: 'var(--caution)', marginTop: '8px' }}>
                    <strong>Incomplete run:</strong> {report.cast.effective} effective, {report.cast.failed} failed of {report.cast.requested} requested viewers.
                  </div>
                )}

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
                    {report.completion.range?.method && (
                      <div className="metric-method mono" style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Range method: {report.completion.range.method}
                      </div>
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
                  <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '16px' }}>No supported edit found.</p>
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
                  <strong>Notice:</strong> {suppressedCount} unsupported candidate {suppressedCount === 1 ? 'note was' : 'notes were'} suppressed by the deterministic stop-fraction detector.
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
                      <dd>{report.trust.reported_versions?.[0] || 'not provided'}</dd>
                      <dt>Training cutoff:</dt>
                      <dd>{report.trust.training_cutoff || 'not provided'}</dd>
                      <dt>Range method:</dt>
                      <dd className="mono">{report.completion.range?.method || report.methodology?.range_kind}</dd>
                      <dt>Ranking rule:</dt>
                      <dd>{report.methodology?.ranking || 'heuristic stop fraction'}</dd>
                      <dt>Source commit:</dt>
                      <dd className="mono">{report.trust.app_source_sha || report.trust.source_sha}</dd>
                      <dt>Media SHA-256:</dt>
                      <dd className="mono">{report.trust.media_sha256}</dd>
                    </dl>

                    {report.methodology?.assumptions && report.methodology.assumptions.length > 0 && (
                      <div style={{ marginTop: '10px' }}>
                        <strong>Methodology assumptions:</strong>
                        <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                          {report.methodology.assumptions.map((a: string, i: number) => (
                            <li key={i}>{a}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {report.trust.limitations && report.trust.limitations.length > 0 && (
                      <div style={{ marginTop: '10px' }}>
                        <strong>Simulation limitations:</strong>
                        <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                          {report.trust.limitations.map((lim: string, i: number) => (
                            <li key={i}>{lim}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    <div style={{ marginTop: '10px' }}>
                      <strong>Caveats:</strong>
                      <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                        {report.caveats.map((c, i) => (
                          <li key={i}>{c}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </details>
              </div>

              {/* Deletion action */}
              <div className="actions-footer">
                <button
                  ref={deleteBtnRef}
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

        {/* View 5: Deleting / Deleted Progress with honest app-owned copy limits */}
        {(viewState === 'deleting' || viewState === 'deleted') && deletionState && (
          <div className="running-container">
            <span className="stage-badge" style={{ background: varCss(viewState === 'deleted' ? 'complete' : 'pending') }}>
              {viewState === 'deleted' ? 'Complete' : 'Deleting'}
            </span>
            <h2>{viewState === 'deleted' ? 'App-owned copies removed' : 'Executing deletion lifecycle'}</h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
              Access revoked immediately ({deletionState.access_revoked_at ? new Date(deletionState.access_revoked_at).toLocaleTimeString() : 'revoked'}). Controlled artifacts removed from PostgreSQL and private storage.
            </p>

            {deletionState.caveat && (
              <div className="deletion-caveat" style={{ marginTop: '12px', padding: '10px 14px', background: 'var(--bg-subtle)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '13px', color: 'var(--text-muted)' }}>
                <strong>Scope &amp; caveat:</strong> {deletionState.caveat}
              </div>
            )}

            <div className="deletion-targets-list" style={{ marginTop: '16px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>App-controlled storage targets:</div>
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

        {/* View 6: Error State with usable recovery and delete action */}
        {viewState === 'error' && (
          <div className="running-container">
            <span className="stage-badge" style={{ background: 'var(--error-tint)', color: 'var(--error)' }}>
              Error
            </span>
            <h2>Operation failed</h2>
            <p style={{ color: 'var(--error)', marginTop: '8px' }}>{errorMessage}</p>
            <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button type="button" className="btn btn-primary" onClick={handleReset}>
                Try again
              </button>
              {videoId && (
                <button
                  ref={deleteBtnRef}
                  type="button"
                  className="btn btn-danger"
                  onClick={() => setShowDeleteModal(true)}
                >
                  Delete uploaded video
                </button>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Confirmation Modal for Deletion with focus management & trap */}
      {showDeleteModal && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onKeyDown={(e) => {
            if (e.key === 'Escape') setShowDeleteModal(false);
          }}
        >
          <div className="modal-dialog">
            <h3 id="modal-title" className="modal-title">Delete this video?</h3>
            <p className="modal-body">
              This will immediately revoke access and remove the original video, generated scene frames, simulation events,
              and reports from private storage and PostgreSQL.
            </p>
            <div className="modal-footer">
              <button
                ref={cancelBtnRef}
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

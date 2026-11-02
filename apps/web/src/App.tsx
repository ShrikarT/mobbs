import React, { useEffect, useState, useRef, useMemo } from 'react';
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
  fetchAnalysis,
  fetchEvidence,
} from './api';
import {
  SessionResponse,
  RunState,
  ReportData,
  DeletionState,
  NoteItem,
  SimulationEvent,
  RetentionRow,
  MetricItem,
  EvidenceItem,
} from './types';

function formatUnavailableReason(code?: string | null): string {
  if (!code) return 'Not observed';
  const map: Record<string, string> = {
    confusion_signal_unobserved: 'Confusion signal unobserved',
    cta_understanding_signal_unobserved: 'Call to action signal unobserved',
    action_not_observed_by_legacy_provider: 'Action not observed by provider',
    no_scene_entrants: 'no_scene_entrants',
    trend_signal_unobserved: 'Trend fit signal unobserved',
    unsupported_trigger: 'Trigger not supported by evidence',
    quote_mismatch: 'Quote mismatch',
    invalid_time: 'Invalid timing window',
    invalid_reference: 'Invalid scene reference',
    malformed_candidate: 'Malformed candidate payload',
  };
  return map[code] || code.replace(/_/g, ' ');
}

export function App({
  initialReport,
  initialViewState,
}: {
  initialReport?: ReportData;
  initialViewState?: 'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error';
} = {}) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [sessionError, setSessionError] = useState<string | null>(null);

  // App workflow state: 'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error'
  const [viewState, setViewState] = useState<
    'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error'
  >(initialViewState || (initialReport ? 'ready' : 'idle'));
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Profile choice: 'flash' (50 personas) or 'test' (3 personas)
  const [selectedProfile, setSelectedProfile] = useState<'flash' | 'test'>('flash');
  const [availableProfiles, setAvailableProfiles] = useState<('flash' | 'test')[]>(['flash', 'test']);

  // Active video & run
  const [videoId, setVideoId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const [report, setReport] = useState<ReportData | null>(initialReport || null);

  // Persisted events and live graph state
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [isGraphPaused, setIsGraphPaused] = useState<boolean>(false);
  const bufferedEventsRef = useRef<SimulationEvent[]>([]);

  // Selected note / evidence for player seeking & highlight
  const [selectedNote, setSelectedNote] = useState<NoteItem | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  // Fencing and request cancellation refs to prevent stale async responses
  const runFenceRef = useRef<number>(0);
  const evidenceFenceRef = useRef<number>(0);
  const delFenceRef = useRef<number>(0);
  const pollAbortControllerRef = useRef<AbortController | null>(null);

  const abortActiveRunTasks = () => {
    runFenceRef.current++;
    if (pollAbortControllerRef.current) {
      pollAbortControllerRef.current.abort();
      pollAbortControllerRef.current = null;
    }
  };

  // Deletion modal & tracking
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [deletionState, setDeletionState] = useState<DeletionState | null>(null);
  const cancelBtnRef = useRef<HTMLButtonElement>(null);
  const confirmBtnRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);

  // Modal focus lifecycle: initial Cancel focus, restore trigger on close
  useEffect(() => {
    if (showDeleteModal) {
      setTimeout(() => cancelBtnRef.current?.focus(), 20);
    } else if (triggerRef.current) {
      triggerRef.current.focus();
    }
  }, [showDeleteModal]);

  const handleModalKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      setShowDeleteModal(false);
      return;
    }
    if (e.key === 'Tab') {
      if (e.shiftKey) {
        if (document.activeElement === cancelBtnRef.current) {
          e.preventDefault();
          confirmBtnRef.current?.focus();
        }
      } else {
        if (document.activeElement === confirmBtnRef.current) {
          e.preventDefault();
          cancelBtnRef.current?.focus();
        }
      }
    }
  };

  // Start polling deletion helper with sequenced polling and generation fencing
  const startPollingDeletion = (delId: string) => {
    const currentDelFence = ++delFenceRef.current;
    let delTimer: ReturnType<typeof setTimeout> | null = null;
    let isDelBusy = false;

    const pollDel = async () => {
      if (delFenceRef.current !== currentDelFence || isDelBusy) return;
      isDelBusy = true;
      try {
        const cur = await fetchDeletion(delId);
        if (delFenceRef.current !== currentDelFence) return;
        setDeletionState(cur);
        if (cur.status === 'complete' && cur.can_claim_complete) {
          setViewState('deleted');
          return;
        }
      } catch (err: any) {
        if (delFenceRef.current !== currentDelFence) return;
        if (err.status === 401 || err.status === 404) {
          setErrorMessage('Deletion tracking unavailable or session expired.');
          setViewState('error');
          return;
        }
      } finally {
        isDelBusy = false;
        if (delFenceRef.current === currentDelFence) {
          delTimer = setTimeout(pollDel, 1000);
        }
      }
    };

    delTimer = setTimeout(pollDel, 1000);
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
            const vid = vids[0].id;
            setVideoId(vid);

            // Fetch video analysis for profile availability
            try {
              const analysis = await fetchAnalysis(vid);
              if (analysis.available_profiles) {
                setAvailableProfiles(analysis.available_profiles);
                if (!analysis.available_profiles.includes('flash')) {
                  setSelectedProfile('test');
                }
              }
            } catch {}

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

  // Poll / SSE for run updates when processing with non-overlapping requests and generation fencing
  useEffect(() => {
    if (viewState !== 'processing' || !runId) return;

    let isMounted = true;
    const currentFence = ++runFenceRef.current;
    const abortCtrl = new AbortController();
    pollAbortControllerRef.current = abortCtrl;
    const activeRunId = runId;

    let pollTimeout: ReturnType<typeof setTimeout> | null = null;
    let isPollBusy = false;
    let eventSource: EventSource | null = null;

    // Helper: Drain terminal events from server before completing
    const drainTerminalEvents = async (lastSeq: number) => {
      if (!isMounted || runFenceRef.current !== currentFence) return;
      try {
        const res = await fetch(`/runs/${activeRunId}/events?after=${lastSeq}`, {
          signal: abortCtrl.signal,
        });
        if (!res.ok) return;
        const text = await res.text();
        if (!isMounted || runFenceRef.current !== currentFence) return;
        const lines = text.split('\n');
        const newEvents: SimulationEvent[] = [];
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const parsed = JSON.parse(line.slice(6));
              if (parsed && parsed.event_id) {
                newEvents.push(parsed);
              }
            } catch {}
          }
        }
        if (newEvents.length > 0 && isMounted && runFenceRef.current === currentFence) {
          setEvents((prev) => {
            const map = new Map<string, SimulationEvent>();
            for (const ev of prev) map.set(ev.event_id, ev);
            for (const ev of newEvents) map.set(ev.event_id, ev);
            return Array.from(map.values()).sort((a, b) => a.sequence - b.sequence);
          });
        }
      } catch {}
    };

    const scheduleNextPoll = (delayMs: number) => {
      if (!isMounted || runFenceRef.current !== currentFence) return;
      pollTimeout = setTimeout(pollRun, delayMs);
    };

    const pollRun = async () => {
      if (!isMounted || runFenceRef.current !== currentFence || isPollBusy) return;
      isPollBusy = true;
      try {
        const state = await fetchRun(activeRunId, abortCtrl.signal);
        if (!isMounted || runFenceRef.current !== currentFence) return;
        setRunState(state);

        // Surface report for complete OR incomplete terminal state
        if (state.status === 'complete' || state.status === 'incomplete') {
          // Terminal drain: ensure all final events are captured
          const highestSeq = events.length > 0 ? Math.max(...events.map((e) => e.sequence)) : 0;
          await drainTerminalEvents(highestSeq);
          if (!isMounted || runFenceRef.current !== currentFence) return;

          const repResult = await fetchReport(activeRunId, abortCtrl.signal);
          if (!isMounted || runFenceRef.current !== currentFence) return;

          if (repResult.ready && repResult.report) {
            setReport(repResult.report);
            if (repResult.report.notes.length > 0) {
              setSelectedNote(repResult.report.notes[0]);
            }
            setViewState('ready');
            return; // terminal state reached, do not reschedule
          }
        } else if (state.status === 'failed') {
          setErrorMessage(state.error_code || 'Analysis failed');
          setViewState('error');
          return; // terminal failure, do not reschedule
        }
      } catch (err: any) {
        if (err.name === 'AbortError' || !isMounted || runFenceRef.current !== currentFence) {
          return; // request was aborted or superseded by newer generation
        }
        if (err.status === 401) {
          setSessionError('Session expired. Please start a new session.');
          setViewState('error');
          return;
        } else if (err.status === 404) {
          setErrorMessage('Run not found or was deleted.');
          setViewState('error');
          return;
        }
      } finally {
        isPollBusy = false;
        if (isMounted && runFenceRef.current === currentFence) {
          scheduleNextPoll(1000);
        }
      }
    };

    // Trigger initial poll immediately
    scheduleNextPoll(0);

    // Connect to SSE events stream with cursor and named event handlers
    try {
      const lastSeq = events.length > 0 ? Math.max(...events.map((e) => e.sequence)) : 0;
      eventSource = new EventSource(`/runs/${activeRunId}/events${lastSeq ? `?after=${lastSeq}` : ''}`);

      const handleEvent = (e: MessageEvent) => {
        if (!isMounted || runFenceRef.current !== currentFence) return;
        try {
          const parsed = JSON.parse(e.data);
          if (parsed && parsed.event_id) {
            const evItem: SimulationEvent = {
              event_id: parsed.event_id,
              sequence: parsed.sequence,
              type: parsed.type,
              payload: parsed.payload || {},
              created_at: parsed.created_at,
            };

            if (isGraphPaused) {
              bufferedEventsRef.current.push(evItem);
            } else {
              setEvents((prev) => {
                if (prev.some((item) => item.event_id === evItem.event_id)) return prev;
                return [...prev, evItem].sort((a, b) => a.sequence - b.sequence);
              });
            }
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
      abortCtrl.abort();
      if (pollTimeout) clearTimeout(pollTimeout);
      if (eventSource) eventSource.close();
    };
  }, [viewState, runId, isGraphPaused]);

  // Pause / Resume graph presentation helper
  const handleTogglePauseGraph = () => {
    if (isGraphPaused) {
      // Resume: flush all buffered events at once
      const buffered = bufferedEventsRef.current;
      bufferedEventsRef.current = [];
      setIsGraphPaused(false);
      if (buffered.length > 0) {
        setEvents((prev) => {
          const map = new Map<string, SimulationEvent>();
          for (const ev of prev) map.set(ev.event_id, ev);
          for (const ev of buffered) map.set(ev.event_id, ev);
          return Array.from(map.values()).sort((a, b) => a.sequence - b.sequence);
        });
      }
    } else {
      setIsGraphPaused(true);
    }
  };

  // Handle file upload and analysis profile inspection
  const handleUpload = async (file: File) => {
    abortActiveRunTasks();
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

      // Check available profiles for uploaded media
      let profileToUse = selectedProfile;
      try {
        const analysis = await fetchAnalysis(up.video_id);
        if (analysis.available_profiles) {
          setAvailableProfiles(analysis.available_profiles);
          // If user picked flash but this video only supports test (e.g. Video B)
          if (profileToUse === 'flash' && !analysis.available_profiles.includes('flash')) {
            // Respect truthful capability
            profileToUse = 'flash'; // Keep requested so backend returns explicit 422 if unhandled, or handle below
          }
        }
      } catch {}

      setStatusMessage(`Video accepted. Queueing ${profileToUse === 'flash' ? '50-persona Flash' : '3-persona test'} analysis...`);

      const run = await startRun(up.video_id, currentSession.csrf, profileToUse);
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
    setSelectedEvidence(null);
    if (videoRef.current) {
      videoRef.current.currentTime = note.start_ms / 1000;
      videoRef.current.play().catch(() => {});
    }
  };

  // Seek video and view evidence details with fencing against stale responses
  const handleSelectEvidence = async (evId: string) => {
    if (!runId) return;
    const currentFence = runFenceRef.current;
    const targetRunId = runId;
    const currentEvidenceFence = ++evidenceFenceRef.current;

    try {
      const ev = await fetchEvidence(targetRunId, evId);
      if (
        runFenceRef.current === currentFence &&
        runId === targetRunId &&
        evidenceFenceRef.current === currentEvidenceFence &&
        viewState === 'ready'
      ) {
        setSelectedEvidence(ev);
        if (videoRef.current && ev.start_ms !== undefined) {
          videoRef.current.currentTime = ev.start_ms / 1000;
          videoRef.current.play().catch(() => {});
        }
      }
    } catch {}
  };

  // Trigger deletion
  const handleDelete = async () => {
    if (!videoId || !session) return;
    abortActiveRunTasks();
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
    abortActiveRunTasks();
    delFenceRef.current++;
    setVideoId(null);
    setRunId(null);
    setRunState(null);
    setReport(null);
    setSelectedNote(null);
    setSelectedEvidence(null);
    setEvents([]);
    bufferedEventsRef.current = [];
    setIsGraphPaused(false);
    setDeletionState(null);
    setErrorMessage(null);
    setViewState('idle');
  };

  // Authoritative stored scenes and duration derivation
  const scenes = report?.scenes && report.scenes.length > 0 ? report.scenes : [];
  const durationMs = report?.duration_ms ?? (scenes.length > 0 ? scenes[scenes.length - 1].end_ms : null);
  const durationSec = durationMs !== null ? (durationMs / 1000).toFixed(1) : null;

  // Suppressed notes count derived from backend data
  const suppressedCount = useMemo(() => {
    if (!report) return 0;
    if (report.note_rejections) {
      return Object.values(report.note_rejections).reduce((a, b) => a + b, 0);
    }
    if (report.suppressed_notes !== undefined) {
      return report.suppressed_notes;
    }
    const match = report.caveats?.find((c) => c.includes('unsupported note'))?.match(/(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  }, [report]);

  // Derive persona state map for the live graph using persisted reason
  const personaStateMap = useMemo(() => {
    const map = new Map<
      string,
      {
        status: 'watching' | 'stopped' | 'active';
        lastScene: number;
        atMs?: number;
        reason?: string;
        actions: string[];
      }
    >();

    for (const ev of events) {
      const p = ev.payload;
      if (!p || !p.persona_id) continue;
      const current = map.get(p.persona_id) || {
        status: 'watching',
        lastScene: p.scene_id,
        atMs: p.at_ms,
        actions: [],
      };

      current.lastScene = Math.max(current.lastScene, p.scene_id);
      if (p.at_ms !== undefined) current.atMs = p.at_ms;

      if (ev.type === 'persona.stopped') {
        current.status = 'stopped';
        current.reason = p.reason || p.drop_reason;
      } else if (ev.type === 'persona.continued') {
        current.status = 'watching';
        current.reason = p.reason;
      }

      if (p.actions && Array.isArray(p.actions)) {
        for (const act of p.actions) {
          const actType = typeof act === 'object' && act ? act.type : String(act);
          if (actType && !current.actions.includes(actType)) {
            current.actions.push(actType);
          }
        }
      }
      map.set(p.persona_id, current);
    }
    return map;
  }, [events]);

  // List of all expected persona IDs based on requested count
  const allExpectedPersonaIds = useMemo(() => {
    const requested = runState?.requested || (selectedProfile === 'flash' ? 50 : 3);
    return Array.from({ length: requested }, (_, i) => `p${String(i + 1).padStart(3, '0')}`);
  }, [runState, selectedProfile]);

  // Derive effective mode: saved report provenance first, sealed manifest second, session config only for initial empty state
  const effectiveMode = useMemo(() => {
    if (report?.trust?.mode) return report.trust.mode;
    if (runState?.manifest?.provider_mode) return runState.manifest.provider_mode;
    return session?.provider_mode || 'recorded';
  }, [report?.trust?.mode, runState?.manifest?.provider_mode, session?.provider_mode]);

  return (
    <div>
      {/* 56px utility header with responsive wrap at 320px */}
      <header className="app-header">
        <div className="brand-group">
          <span className="brand-title">Viralist / Evidence desk</span>
          {effectiveMode === 'standard' ? (
            <span className="badge-recorded" style={{ background: '#2e1065', borderColor: '#7c3aed', color: '#e9d5ff' }}>
              Standard mode · Meta muse-spark-1.3
            </span>
          ) : (
            <span className="badge-recorded">Recorded mode · Standard Meta Spark 1.3</span>
          )}
        </div>
        <div className="header-meta">
          {session ? (
            <span className="session-badge mono">Session: {session.retention_hours}h retention</span>
          ) : (
            <span className="session-badge">Initializing session...</span>
          )}
        </div>
      </header>

      <main className="app-main">
        {sessionError && (
          <div className="alert-box error" role="alert">
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

            {/* Profile Selection */}
            <div className="profile-selector-box" role="group" aria-label="Audience simulation profile">
              <span className="selector-title">Simulation Profile:</span>
              <div className="profile-options">
                <button
                  type="button"
                  className={`btn-toggle ${selectedProfile === 'flash' ? 'active' : ''}`}
                  onClick={() => setSelectedProfile('flash')}
                  aria-pressed={selectedProfile === 'flash'}
                >
                  <span className="btn-toggle-title">Flash (50 personas)</span>
                  <span className="btn-toggle-desc">Full sequential simulation · Hook &amp; Pacing · Drop-off curve</span>
                </button>
                <button
                  type="button"
                  className={`btn-toggle ${selectedProfile === 'test' ? 'active' : ''}`}
                  onClick={() => setSelectedProfile('test')}
                  aria-pressed={selectedProfile === 'test'}
                >
                  <span className="btn-toggle-title">Test (3 personas)</span>
                  <span className="btn-toggle-desc">Diagnostic test cast · Fast verification</span>
                </button>
              </div>
            </div>

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
              <strong>V03 Workbench Operating Disclosure</strong>
              <ul className="disclosure-list">
                <li>Server validates MP4 container, codec, and duration before any dispatch.</li>
                <li>Simulated personas: 50 instances for Flash, 3 for Test. All audience outcomes are simulated models, never real people.</li>
                {effectiveMode === 'standard' ? (
                  <li>Live Standard provider inference via Meta muse-spark-1.3; bounded calls per run with concurrency {selectedProfile === 'flash' ? 8 : 1}. Simulation is sequential scene-by-scene per persona without native whole-video understanding, audio extraction, or human calibration.</li>
                ) : (
                  <li>Exact hash-bound recorded inference; no new provider latency or spend claimed.</li>
                )}
                <li>All uploaded video files, derivatives, and reports can be deleted at any time with access revoked immediately.</li>
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

        {/* View 3: Processing / Simulating with Live Persona Graph */}
        {viewState === 'processing' && (
          <div className="running-container wide">
            <div className="processing-header">
              <span className="stage-badge">{runState?.stage || 'decoding'}</span>
              <h2>Analyzing audience retention</h2>
              <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
                Stage: <strong className="mono">{runState?.stage || 'decoding'}</strong> · Cast:{' '}
                {runState?.requested || (selectedProfile === 'flash' ? 50 : 3)} requested ·{' '}
                {runState?.effective ?? 0} finished · {runState?.pending ?? (selectedProfile === 'flash' ? 50 : 3)} active
                {runState?.failed ? ` · ${runState.failed} failed` : ''}
              </p>
            </div>

            <div className="progress-track" role="progressbar" aria-label="Analyzing audience retention" aria-busy="true">
              <div className="progress-bar indeterminate"></div>
            </div>

            {/* Live 50-Persona Grid / Graph */}
            <div className="live-graph-panel">
              <div className="graph-controls-header">
                <div className="graph-title-group">
                  <strong>Simulated Audience Grid ({events.length} decisions observed):</strong>
                  <span className="graph-subtext">Word + shape + color encoded state per persona</span>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleTogglePauseGraph}
                  aria-pressed={isGraphPaused}
                >
                  {isGraphPaused ? '▶ Resume view' : '⏸ Pause view'}
                </button>
              </div>

              {isGraphPaused && (
                <div className="graph-paused-banner" role="status">
                  Live display paused. Ingestion and background simulation continue normally. Click Resume to view all latest events.
                </div>
              )}

              {/* Persona Node Grid */}
              <div className="persona-grid" role="region" aria-label="Simulated personas state grid">
                {allExpectedPersonaIds.map((pid) => {
                  const state = personaStateMap.get(pid);
                  const isStopped = state?.status === 'stopped';
                  const isWatching = state?.status === 'watching';
                  const hasActions = state?.actions && state.actions.length > 0;
                  const reasonText = state?.reason ? ` · Quote: "${state.reason}"` : '';

                  return (
                    <div
                      key={pid}
                      className={`persona-node ${isStopped ? 'stopped' : isWatching ? 'watching' : 'pending'}`}
                      title={`${pid}: ${isStopped ? `Stopped (scene ${state?.lastScene})${reasonText}` : isWatching ? `Watching (scene ${state?.lastScene})${reasonText}` : 'Pending'}`}
                    >
                      <span className="persona-id mono">{pid}</span>
                      <span className={`persona-indicator ${isStopped ? 'indicator-stopped' : isWatching ? 'indicator-watching' : 'indicator-pending'}`}>
                        {isStopped ? '■ STOP' : isWatching ? '● WATCH' : '○ WAIT'}
                      </span>
                      {hasActions && (
                        <div className="node-action-badges">
                          {state?.actions.map((act) => (
                            <span key={act} className="mini-action-badge" title={act}>
                              {act === 'like' ? '♥' : act === 'share' ? '↗' : act === 'save' ? '★' : '💬'}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {/* Accessible Ordered Event Log */}
              <details className="event-log-details">
                <summary className="event-log-summary">
                  Ordered event sequence log ({events.length} persisted records)
                </summary>
                <div className="event-log-feed mono">
                  {events.length === 0 ? (
                    <div className="event-feed-empty">Awaiting scene checkpoints...</div>
                  ) : (
                    events.map((ev) => {
                      const p = ev.payload;
                      const isStop = ev.type === 'persona.stopped';
                      return (
                        <div key={ev.event_id} className={`event-log-item ${isStop ? 'event-stop' : 'event-continue'}`}>
                          <span className="ev-seq">#{ev.sequence}</span>
                          <span className="ev-type">{ev.type}</span>
                          <span className="ev-pid mono">{p.persona_id}</span>
                          <span className="ev-scene">scene {p.scene_id}</span>
                          {p.at_ms !== undefined && <span className="ev-time">{p.at_ms}ms</span>}
                          {p.reason && (
                            <span className="ev-reason">
                              {isStop ? 'stop quote: ' : 'quote: '}&ldquo;{p.reason}&rdquo;
                            </span>
                          )}
                          {p.actions && p.actions.length > 0 && (
                            <span className="ev-actions">
                              actions: {p.actions.map((a) => (typeof a === 'object' && a ? a.type : String(a))).join(', ')}
                            </span>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </details>
            </div>

            <div style={{ marginTop: '24px', display: 'flex', justifyContent: 'center' }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={(e) => {
                  triggerRef.current = e.currentTarget;
                  setShowDeleteModal(true);
                }}
              >
                Cancel &amp; delete video
              </button>
            </div>
          </div>
        )}

        {/* View 4: Report Workbench */}
        {viewState === 'ready' && report && (
          <div className="workbench-grid">
            {/* Left: Video player, interactive timeline, & retention drop-off table */}
            <div className="player-column">
              <div className="video-container">
                <video
                  ref={videoRef}
                  src={`/videos/${videoId}/media`}
                  controls
                  playsInline
                  preload="auto"
                  aria-label="Uploaded video preview"
                  className="video-element"
                />
              </div>

              {/* Interactive Timeline Scrubber */}
              <div className="timeline-card">
                <div className="timeline-header">
                  <span>Scene timeline {scenes.length > 0 ? `(${scenes.length} scenes)` : '(scenes unavailable)'}</span>
                  <span className="mono">{durationSec !== null ? `0.0s – ${durationSec}s` : 'Duration unavailable'}</span>
                </div>
                {scenes.length > 0 ? (
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
                ) : (
                  <div className="timeline-unavailable">
                    Scene boundaries unavailable for this legacy report.
                  </div>
                )}
              </div>

              {/* Retention & Drop-Off Table / Curve */}
              {report.retention && report.retention.length > 0 ? (
                <div className="retention-card">
                  <div className="retention-header">
                    <h3>Scene Retention &amp; Drop-Off ({report.retention.length} scenes)</h3>
                    <span className="mono text-muted">200 whole-persona resamples · p10–p90</span>
                  </div>
                  <div className="retention-table-container">
                    <table className="retention-table">
                      <thead>
                        <tr>
                          <th>Scene</th>
                          <th>Timing</th>
                          <th>Entrants</th>
                          <th>Stopped</th>
                          <th>Survival Rate</th>
                          <th>Drop Rate</th>
                        </tr>
                      </thead>
                      <tbody>
                        {report.retention.map((row: RetentionRow) => {
                          const sSec = (row.start_ms / 1000).toFixed(1);
                          const eSec = (row.end_ms / 1000).toFixed(1);
                          const survObs = row.survival.observed !== null && row.survival.observed !== undefined ? `${row.survival.observed?.toFixed(1)}%` : 'Unavailable';
                          const survRange = row.survival.range ? `[${row.survival.range.low.toFixed(0)}%–${row.survival.range.high.toFixed(0)}%]` : '';

                          // Honest zero-entrant disclosure
                          const dropObs = row.drop_rate.observed !== null && row.drop_rate.observed !== undefined
                            ? `${row.drop_rate.observed?.toFixed(1)}%`
                            : 'Unavailable';
                          const dropReason = row.drop_rate.unavailable_reason
                            ? ` (${formatUnavailableReason(row.drop_rate.unavailable_reason)})`
                            : '';
                          const dropRange = row.drop_rate.range ? `[${row.drop_rate.range.low.toFixed(0)}%–${row.drop_rate.range.high.toFixed(0)}%]` : '';

                          return (
                            <tr key={row.scene_id}>
                              <td className="mono">Scene {row.scene_id}</td>
                              <td className="mono">{sSec}s–{eSec}s</td>
                              <td className="mono">{row.entrants}</td>
                              <td className="mono">{row.stopped}</td>
                              <td className="mono">
                                <strong>{survObs}</strong> {survRange && <span className="range-text">{survRange}</span>}
                              </td>
                              <td className="mono">
                                <strong>{dropObs}</strong>
                                {dropRange && <span className="range-text">{dropRange}</span>}
                                {dropReason && <span className="unavailable-tag">{dropReason}</span>}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="retention-card">
                  <div className="retention-header">
                    <h3>Scene Retention &amp; Drop-Off</h3>
                  </div>
                  <div className="section-unavailable-banner">
                    Scene retention curve unavailable: report does not contain retention intervals.
                  </div>
                </div>
              )}
            </div>

            {/* Right: Evidence, Findings, Scores, Notes, & Provenance */}
            <div className="evidence-column">
              <div className="report-header">
                <h2 className="verdict-title">Executive finding</h2>
                <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginBottom: '16px' }}>
                  Audience retention simulation with {report.cast.effective} simulated synthetic personas.
                </p>

                {/* Cohort coverage disclosure */}
                <div className="cohort-coverage-card">
                  {report.cast.effective < report.cast.requested || report.cast.status !== 'complete' || report.cast.failed > 0 || report.cast.pending > 0 ? (
                    <div className="alert-box caution">
                      <strong>Partial cohort:</strong> Simulated {report.cast.effective} of {report.cast.requested} requested personas ({report.cast.failed} failed, {report.cast.pending} pending; status: {report.cast.status}). Metrics represent observed effective sample only, not a complete requested cohort.
                    </div>
                  ) : (
                    <div className="cohort-complete-badge mono" style={{ fontSize: '12px', color: 'var(--text-subtle)' }}>
                      Complete cohort: {report.cast.effective} / {report.cast.requested} personas simulated (status: {report.cast.status})
                    </div>
                  )}

                  {report.coverage?.excluded_traces &&
                    ((report.coverage.excluded_traces.failed && report.coverage.excluded_traces.failed.length > 0) ||
                      (report.coverage.excluded_traces.pending && report.coverage.excluded_traces.pending.length > 0)) && (
                      <div className="excluded-traces-alert mono" style={{ fontSize: '12px', marginTop: '6px', color: 'var(--caution)' }}>
                        <strong>Excluded traces:</strong>{' '}
                        {report.coverage.excluded_traces.failed && report.coverage.excluded_traces.failed.length > 0 &&
                          `Failed: [${report.coverage.excluded_traces.failed.join(', ')}] `}
                        {report.coverage.excluded_traces.pending && report.coverage.excluded_traces.pending.length > 0 &&
                          `Pending: [${report.coverage.excluded_traces.pending.join(', ')}]`}
                      </div>
                    )}
                </div>

                {/* Approved hierarchy: Editing finding / Notes appear BEFORE metric grids */}
                <div className="primary-finding-section" style={{ marginBottom: '20px' }}>
                  {report.notes.length === 0 ? (
                    <div className="no-notes-banner">
                      <p style={{ color: 'var(--text-primary)', fontSize: '16px', fontWeight: 600, marginBottom: '6px' }}>
                        No supported edit found.
                      </p>
                      <div style={{ color: 'var(--text-muted)', fontSize: '13px', lineHeight: '1.4', marginBottom: '10px' }}>
                        {report.observations && report.observations.length > 0 ? (
                          <span>
                            Observed drop triggers evaluated: {report.observations.map((obs) => {
                              const pct = (obs.value * 100).toFixed(1);
                              const threshPct = (obs.threshold * 100).toFixed(1);
                              return `Scene ${obs.scene_id} (${(obs.start_ms / 1000).toFixed(1)}s–${(obs.end_ms / 1000).toFixed(1)}s: ${obs.numerator}/${obs.denominator} stopped, ${pct}%, threshold ${threshPct}%)`;
                            }).join('; ')}. No candidate director notes satisfied the deterministic support criteria for these triggers.
                          </span>
                        ) : (
                          <span>
                            Observed dropout triggers are unavailable for this report.
                          </span>
                        )}
                      </div>
                      {report.observations && report.observations.length > 0 && (
                        <div className="suppressed-note-alert">
                          <strong>Notice:</strong> {suppressedCount} unsupported candidate {suppressedCount === 1 ? 'note was' : 'notes were'} suppressed by the deterministic stop-fraction detector.
                          Only findings backed by observed dropout triggers are surfaced.
                          {report.note_rejections && (
                            <div className="rejection-breakdown mono" style={{ fontSize: '11px', marginTop: '6px' }}>
                              Rejection breakdown: unsupported_trigger: {report.note_rejections.unsupported_trigger} (Trigger not supported), quote_mismatch: {report.note_rejections.quote_mismatch}, invalid_time: {report.note_rejections.invalid_time}, invalid_reference: {report.note_rejections.invalid_reference}, malformed: {report.note_rejections.malformed_candidate}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div>
                      <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '12px' }}>
                        Director&apos;s Notes ({report.notes.length})
                      </h3>
                      {report.notes.map((note) => (
                        <div
                          key={note.id}
                          className={`note-card ${selectedNote?.id === note.id ? 'selected' : ''}`}
                          onClick={() => handleSelectNote(note)}
                          tabIndex={0}
                          role="region"
                          onKeyDown={(e) => {
                            if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) {
                              e.preventDefault();
                              handleSelectNote(note);
                            }
                          }}
                          aria-label={`Note at ${(note.start_ms / 1000).toFixed(1)} seconds: ${note.interpretation}`}
                        >
                          <div className="note-timestamp mono">
                            {(note.start_ms / 1000).toFixed(1)}s – {(note.end_ms / 1000).toFixed(1)}s (Click note to seek)
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
                                <button
                                  key={q.evidence_id || idx}
                                  type="button"
                                  className="quote-button"
                                  aria-label={`Inspect evidence quote ${idx + 1}: "${q.text}"`}
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleSelectEvidence(q.evidence_id);
                                  }}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter' || e.key === ' ') {
                                      e.stopPropagation();
                                    }
                                  }}
                                  title="Click or press Enter/Space to inspect evidence and seek player"
                                >
                                  &ldquo;{q.text}&rdquo;
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}

                      {/* Evidence Inspector Card */}
                      {selectedEvidence && (
                        <div className="evidence-inspector-card">
                          <div className="inspector-header">
                            <strong>Evidence Inspector: {selectedEvidence.id}</strong>
                            <button
                              type="button"
                              className="btn-close-sm"
                              onClick={() => setSelectedEvidence(null)}
                              aria-label="Close evidence inspector"
                            >
                              ✕
                            </button>
                          </div>
                          <div className="inspector-body mono">
                            <div>Persona: <strong>{selectedEvidence.persona_id}</strong></div>
                            <div>Scene: <strong>Scene {selectedEvidence.scene_id} ({selectedEvidence.start_ms}ms–{selectedEvidence.end_ms}ms)</strong></div>
                            <div>Still watching: <strong>{selectedEvidence.still_watching ? 'Yes' : 'No (Dropped)'}</strong></div>
                            {selectedEvidence.reason && <div>Reason: &ldquo;{selectedEvidence.reason}&rdquo;</div>}
                            {selectedEvidence.quote && <div>Quote: &ldquo;{selectedEvidence.quote}&rdquo;</div>}
                          </div>
                        </div>
                      )}

                      {report.observations && report.observations.length > 0 && (
                        <div className="suppressed-note-alert">
                          <strong>Notice:</strong> {suppressedCount} unsupported candidate {suppressedCount === 1 ? 'note was' : 'notes were'} suppressed by the deterministic stop-fraction detector.
                          Only findings backed by observed dropout triggers are surfaced.
                          {report.note_rejections && (
                            <div className="rejection-breakdown mono" style={{ fontSize: '11px', marginTop: '6px' }}>
                              Rejection breakdown: unsupported_trigger: {report.note_rejections.unsupported_trigger} (Trigger not supported), quote_mismatch: {report.note_rejections.quote_mismatch}, invalid_time: {report.note_rejections.invalid_time}, invalid_reference: {report.note_rejections.invalid_reference}, malformed: {report.note_rejections.malformed_candidate}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Simulated cast metrics summary */}
                <div className="metrics-summary">
                  <div className="metric-pill">
                    Cast: <strong>{report.cast.effective} / {report.cast.requested} viewers</strong> ({report.cast.effective < report.cast.requested ? 'Partial cohort' : 'Complete cohort'} · {report.cast.profile} profile · synthetic)
                  </div>
                  <div className="metric-pill">
                    Completion rate:{' '}
                    <strong>{report.completion.observed !== null && report.completion.observed !== undefined ? `${report.completion.observed?.toFixed(1)}%` : 'Unavailable'}</strong>
                    {report.completion.observed !== null && report.completion.observed !== undefined && (
                      <span className="mono" style={{ color: 'var(--text-subtle)' }}>
                        {' '}({report.completion.denominator ? `${Math.round(((report.completion.observed || 0) / 100) * report.completion.denominator)} / ${report.completion.denominator}` : `${report.cast.effective - report.cast.stopped} / ${report.cast.effective}`})
                      </span>
                    )}
                    {report.completion.range && (
                      <span className="mono" style={{ color: 'var(--text-subtle)' }}>
                        {' '}[{report.completion.range.low.toFixed(0)}%–{report.completion.range.high.toFixed(0)}%]
                      </span>
                    )}
                    {report.completion.range?.method && (
                      <div className="metric-method mono">
                        nearest-rank {report.completion.range.method}
                      </div>
                    )}
                  </div>
                  <div className="metric-pill">
                    Stopped viewers: <strong>{report.cast.stopped} / {report.cast.effective}</strong> ({report.cast.effective > 0 ? ((report.cast.stopped / report.cast.effective) * 100).toFixed(1) : '0.0'}%)
                  </div>
                </div>

                {/* Score Indices: Hook, Pacing, and unobserved signals */}
                {report.scores ? (
                  <div className="scores-card">
                    <h3 className="section-subheading">Retention &amp; Quality Indices</h3>
                    <div className="scores-grid">
                      <div className="score-item">
                        <span className="score-label">Hook Score (min 3s)</span>
                        <span className="score-value mono">
                          {report.scores.hook?.observed !== null && report.scores.hook?.observed !== undefined ? `${report.scores.hook?.observed?.toFixed(1)}%` : 'Unavailable'}
                        </span>
                        <span className="score-denominator mono" style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                          {report.scores.hook?.denominator !== null && report.scores.hook?.denominator !== undefined
                            ? `(denominator: ${report.scores.hook.denominator})`
                            : '(denominator unavailable)'}
                        </span>
                        {report.scores.hook?.range && (
                          <span className="score-range mono">
                            [{report.scores.hook.range.low.toFixed(0)}%–{report.scores.hook.range.high.toFixed(0)}%]
                          </span>
                        )}
                      </div>
                      <div className="score-item">
                        <span className="score-label">Pacing Score (80% dur)</span>
                        <span className="score-value mono">
                          {report.scores.pacing?.observed !== null && report.scores.pacing?.observed !== undefined ? `${report.scores.pacing?.observed?.toFixed(1)}%` : 'Unavailable'}
                        </span>
                        <span className="score-denominator mono" style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                          {report.scores.pacing?.denominator !== null && report.scores.pacing?.denominator !== undefined
                            ? `(denominator: ${report.scores.pacing.denominator})`
                            : '(denominator unavailable)'}
                        </span>
                        {report.scores.pacing?.range && (
                          <span className="score-range mono">
                            [{report.scores.pacing.range.low.toFixed(0)}%–{report.scores.pacing.range.high.toFixed(0)}%]
                          </span>
                        )}
                      </div>
                      <div className="score-item unavailable">
                        <span className="score-label">Clarity Index</span>
                        <span className="score-tag">Unavailable</span>
                        <span className="score-reason">{formatUnavailableReason(report.scores.clarity?.unavailable_reason)}</span>
                      </div>
                      <div className="score-item unavailable">
                        <span className="score-label">CTA Index</span>
                        <span className="score-tag">Unavailable</span>
                        <span className="score-reason">{formatUnavailableReason(report.scores.cta?.unavailable_reason)}</span>
                      </div>
                      <div className="score-item unavailable">
                        <span className="score-label">Trend Fit</span>
                        <span className="score-tag">Unavailable</span>
                        <span className="score-reason">{formatUnavailableReason(report.scores.trend?.unavailable_reason)}</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="scores-card">
                    <h3 className="section-subheading">Retention &amp; Quality Indices</h3>
                    <div className="section-unavailable-banner">
                      Quality indices unavailable: report does not contain score indices.
                    </div>
                  </div>
                )}

                {/* Engagement Rates */}
                {report.engagement ? (
                  <div className="engagement-card">
                    <h3 className="section-subheading">Engagement Actions (Simulated personas taking action)</h3>
                    <div className="engagement-grid">
                      {(['like', 'share', 'save', 'comment', 'follow'] as const).map((act) => {
                        const item: MetricItem | undefined = report.engagement?.[act];
                        if (!item) return null;
                        const isUnavail = item.observed === null || item.observed === undefined;
                        const den = item.denominator ?? report.cast.effective;
                        const actionCount = !isUnavail && den ? Math.round(((item.observed || 0) / 100) * den) : null;
                        return (
                          <div key={act} className={`engagement-item ${isUnavail ? 'unavailable' : ''}`}>
                            <span className="act-name">{act.toUpperCase()}</span>
                            <span className="act-value mono">
                              {isUnavail ? 'Unavailable' : `${item.observed?.toFixed(1)}%`}
                            </span>
                            {!isUnavail && actionCount !== null && (
                              <span className="mono" style={{ fontSize: '11px', color: 'var(--text-subtle)' }}>
                                ({actionCount} / {den})
                              </span>
                            )}
                            {item.range && (
                              <span className="act-range mono">
                                [{item.range.low.toFixed(0)}%–{item.range.high.toFixed(0)}%]
                              </span>
                            )}
                            {item.unavailable_reason && (
                              <span className="act-reason">{formatUnavailableReason(item.unavailable_reason)}</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="engagement-card">
                    <h3 className="section-subheading">Engagement Actions (Simulated personas taking action)</h3>
                    <div className="section-unavailable-banner">
                      Engagement telemetry unavailable: report does not contain action telemetry.
                    </div>
                  </div>
                )}
              </div>

              {/* Trust & Provenance Manifest */}
              <div className="trust-manifest">
                <details>
                  <summary className="trust-summary">Trust manifest &amp; simulation provenance</summary>
                  <div className="trust-details">
                    <dl>
                      <dt>Inference mode:</dt>
                      <dd>{report.trust.mode === 'standard' ? 'Standard inference' : 'Recorded replay'} ({report.trust.label || (report.trust.mode === 'standard' ? 'Standard Meta Spark 1.3' : 'Recorded inference')})</dd>
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
                      {report.trust.mode === 'standard' ? (
                        <>
                          <dt>Provider concurrency:</dt>
                          <dd className="mono">{report.trust.provider_concurrency ?? 1} (sequential scenes per persona)</dd>
                          <dt>Live provider calls:</dt>
                          <dd className="mono">{report.trust.live_calls ?? 0}</dd>
                          <dt>Estimated cost (USD):</dt>
                          <dd className="mono">
                            {typeof report.trust.total_cost_usd === 'number'
                              ? `$${report.trust.total_cost_usd.toFixed(6)}`
                              : String(report.trust.total_cost_usd || 'unavailable')}
                          </dd>
                          {report.trust.pricing_version && (
                            <>
                              <dt>Pricing version:</dt>
                              <dd className="mono">{report.trust.pricing_version}</dd>
                            </>
                          )}
                        </>
                      ) : (
                        <>
                          <dt>Live calls / spend:</dt>
                          <dd>0 live calls / $0.00 (Recorded replay)</dd>
                        </>
                      )}
                      {report.trust.feature_sha256 && (
                        <>
                          <dt>Feature SHA-256:</dt>
                          <dd className="mono">{report.trust.feature_sha256}</dd>
                        </>
                      )}
                      {report.trust.cast_sha256 && (
                        <>
                          <dt>Cast SHA-256:</dt>
                          <dd className="mono">{report.trust.cast_sha256}</dd>
                        </>
                      )}
                    </dl>

                    {/* Persona library disclosure - accurate candidate policies without false calibration or archetype claims */}
                    <div className="thin-cast-notice" style={{ marginTop: '12px', padding: '8px 12px', background: 'var(--caution-tint)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', fontSize: '12px', lineHeight: '1.4' }}>
                      {effectiveMode === 'standard' ? (
                        (report.cast.profile === 'flash' || report.manifest?.profile === 'flash') && (report.cast.requested === 50 || report.manifest?.requested === 50) ? (
                          <>
                            <strong>Persona library disclosure:</strong> The Flash 50 cast contains 50 fictional candidate persona policies from fifty-policies.json. This is a synthetic persona library; behavioral distinction was not calibrated against human viewers. Personas evaluate visual frame extractions without live audio, transcript, or OCR processing; intervals represent simulated correlation without causal claims.
                          </>
                        ) : (
                          <>
                            <strong>Persona library disclosure:</strong> The {report.cast.profile === 'test' ? 'Test 3' : `${report.cast.profile} ${report.cast.requested}`} cast contains 3 fictional candidate persona policies. This is a synthetic persona library; behavioral distinction was not calibrated against human viewers. Personas evaluate visual frame extractions without live audio, transcript, or OCR processing; intervals represent simulated correlation without causal claims.
                          </>
                        )
                      ) : (
                        (report.cast.profile === 'flash' || report.manifest?.profile === 'flash') && (report.cast.requested === 50 || report.manifest?.requested === 50) ? (
                          <>
                            <strong>Persona library disclosure:</strong> The Flash 50 cast contains 50 simulated personas derived from five archetypes; this is a synthetic persona library, not 50 distinct human behaviors. Behavioral distinction was not calibrated against human viewers. Personas evaluate visual frame extractions without live audio, transcript, or OCR processing; intervals represent simulated correlation without causal claims.
                          </>
                        ) : (
                          <>
                            <strong>Persona library disclosure:</strong> The {report.cast.profile === 'test' ? 'Test 3' : `${report.cast.profile} ${report.cast.requested}`} cast contains 3 simulated viewers; this is a synthetic persona library and not a representative audience. Behavioral distinction was not calibrated against human viewers. Personas evaluate visual frame extractions without live audio, transcript, or OCR processing; intervals represent simulated correlation without causal claims.
                          </>
                        )
                      )}
                    </div>

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

                    {report.caveats && report.caveats.length > 0 && (
                      <div style={{ marginTop: '10px' }}>
                        <strong>Caveats:</strong>
                        <ul style={{ paddingLeft: '16px', marginTop: '4px' }}>
                          {report.caveats.map((c, i) => (
                            <li key={i}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </details>
              </div>

              {/* Deletion action */}
              <div className="actions-footer">
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={(e) => {
                    triggerRef.current = e.currentTarget;
                    setShowDeleteModal(true);
                  }}
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
            <span
              className="stage-badge"
              style={{
                background:
                  viewState === 'deleted' && deletionState.can_claim_complete
                    ? 'var(--action-green-tint)'
                    : 'var(--caution-tint)',
              }}
            >
              {viewState === 'deleted' && deletionState.can_claim_complete ? 'Complete' : 'Deleting'}
            </span>
            <h2>
              {viewState === 'deleted' && deletionState.can_claim_complete
                ? 'App-owned copies removed'
                : 'Deletion in progress'}
            </h2>
            <p style={{ color: 'var(--text-muted)', marginTop: '8px' }}>
              Access revoked immediately (
              {deletionState.access_revoked_at
                ? new Date(deletionState.access_revoked_at).toLocaleTimeString()
                : 'revoked'}
              ).{' '}
              {viewState === 'deleted' && deletionState.can_claim_complete
                ? 'Controlled artifacts removed from PostgreSQL and private storage.'
                : 'Controlled artifact removal is pending and in progress across PostgreSQL and private storage.'}
            </p>

            {deletionState.caveat && (
              <div className="deletion-caveat">
                <strong>Scope &amp; caveat:</strong> {deletionState.caveat}
              </div>
            )}

            <div className="deletion-targets-list" style={{ marginTop: '16px' }}>
              <div style={{ fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
                App-controlled storage targets{' '}
                {deletionState.pending_targets?.length
                  ? `(${deletionState.pending_targets.length} pending)`
                  : '(all removed)'}
                :
              </div>
              {Object.entries(deletionState.targets).map(([key, target]) => (
                <div key={key} className="target-row">
                  <span className="mono">{key}</span>
                  <span className={`status-badge ${target.status}`}>{target.status}</span>
                </div>
              ))}
            </div>

            {viewState === 'deleted' && deletionState.can_claim_complete && (
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
                  type="button"
                  className="btn btn-danger"
                  onClick={(e) => {
                    triggerRef.current = e.currentTarget;
                    setShowDeleteModal(true);
                  }}
                >
                  Delete uploaded video
                </button>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Confirmation Modal for Deletion with focus management & containment */}
      {showDeleteModal && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
          onKeyDown={handleModalKeyDown}
        >
          <div className="modal-dialog">
            <h3 id="modal-title" className="modal-title">
              Delete this video?
            </h3>
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
                ref={confirmBtnRef}
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

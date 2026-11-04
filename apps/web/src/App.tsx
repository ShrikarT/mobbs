import React, { useEffect, useState, useRef } from 'react';
import {Brand,Doodle} from './Doodles';
import {ScanExperience} from './ScanExperience';
import {ProductReport} from './ProductReport';
import './product.css';
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
  VideoItem,
  RunState,
  ReportData,
  DeletionState,
  NoteItem,
  SimulationEvent,
  EvidenceItem,
  ProvisionalVerdict,
} from './types';

function formatRunErrorMessage(code?: string | null): { title: string; explanation: string; guidance: string } {
  if (!code) {
    return {
      title: 'Analysis could not be completed',
      explanation: 'An unexpected error occurred during processing.',
      guidance: 'Return to upload to start a new analysis. No automatic resend was dispatched.',
    };
  }
  const explanations: Record<string, { title: string; explanation: string; guidance: string }> = {
    uncertain_provider_charge: {
      title: 'Provider response unconfirmed',
      explanation: 'The model provider request timed out or returned an ambiguous transport error. To prevent duplicate billing, automatic retries are paused.',
      guidance: 'Your uploaded video is preserved under your session. No blind retry will be sent.',
    },
    provider_incomplete: {
      title: 'Provider response incomplete',
      explanation: 'The provider returned an unfinished response, so this run stopped.',
      guidance: 'Return to upload to start a new analysis. No automatic resend was dispatched.',
    },
    run_call_ceiling_exceeded: {
      title: 'Call ceiling reached',
      explanation: 'The maximum allowed model inference calls for this run was reached.',
      guidance: 'No further requests were dispatched to avoid extra charges.',
    },
    missing_durable_notes_output: {
      title: 'Notes artifact verification error',
      explanation: 'Stored notes output could not be retrieved from durable storage.',
      guidance: 'Resend was blocked to prevent duplicate billing.',
    },
    corrupted_durable_notes_output: {
      title: 'Notes artifact integrity error',
      explanation: 'Stored notes payload failed cryptographic hash verification.',
      guidance: 'Resend was blocked to prevent duplicate billing.',
    },
    provider_timeout: {
      title: 'Provider request timed out',
      explanation: 'A model inference request timed out before receiving a complete response.',
      guidance: 'Automatic resend was halted to protect against duplicate charges.',
    },
    provider_transport_error: {
      title: 'Network transport error',
      explanation: 'A transport error occurred while contacting the model provider.',
      guidance: 'No unconfirmed retry was sent.',
    },
    saved_scan_unavailable: {
      title: 'Saved scan unavailable',
      explanation: 'This scan was not found in your current session.',
      guidance: 'Return to upload to start a new scan. Your other saved scans remain available.',
    },
    media_preparation_failed: {
      title: 'Audio or video preparation failed',
      explanation: 'The model provider could not finish preparing this video.',
      guidance: 'Your upload is preserved. No automatic request retry was sent.',
    },
    fresh_upload_required_for_multimodal: {
      title: 'A fresh upload is needed',
      explanation: 'This older upload was prepared with the previous visual-only pipeline.',
      guidance: 'Upload it again to run speech transcription and scene-video analysis. Its saved report is preserved.',
    },
    provider_connection_unavailable: {
      title: 'Could not connect to the model provider',
      explanation: 'The connection failed before a request could be sent, including one bounded connection retry.',
      guidance: 'Your upload and saved reactions are preserved. Requests with an unconfirmed provider response are never automatically resent.',
    },
    provider_response_rejected: {
      title: 'Provider response rejected',
      explanation: 'The model provider returned an unexpected payload structure.',
      guidance: 'No automatic retry was sent to protect against unconfirmed charges.',
    },
  };
  return (
    explanations[code] || {
      title: 'Analysis failed',
      explanation: `Operation halted with reason: ${code.replace(/_/g, ' ')}.`,
      guidance: 'Return to upload to start a new analysis. No automatic resend was dispatched.',
    }
  );
}

export function App({
  initialReport,
  initialViewState,
  startFresh = false,
  requestedRunId,
  onRunStarted,
  onNewUpload,
}: {
  initialReport?: ReportData;
  startFresh?: boolean;
  requestedRunId?: string;
  onRunStarted?: (runId:string)=>void;
  onNewUpload?: ()=>void;
  initialViewState?: 'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error';
} = {}) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [savedVideos,setSavedVideos] = useState<VideoItem[]>([]);
  const [sessionError, setSessionError] = useState<string | null>(null);
  const sessionRequestRef=useRef<Promise<SessionResponse>|null>(null);
  const initializeSession=()=>{
    if(!sessionRequestRef.current)sessionRequestRef.current=ensureSession().catch(error=>{
      sessionRequestRef.current=null;throw error;
    });
    return sessionRequestRef.current;
  };

  // App workflow state: 'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error'
  const [viewState, setViewState] = useState<
    'idle' | 'uploading' | 'processing' | 'ready' | 'deleting' | 'deleted' | 'error'
  >(initialViewState || (initialReport ? 'ready' : 'idle'));
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Profile choice: 'flash' (50 personas) or 'test' (3 personas)
  const [selectedProfile, setSelectedProfile] = useState<'flash' | 'test'>('flash');
  const [, setAvailableProfiles] = useState<('flash' | 'test')[]>(['flash', 'test']);

  // Active video & run
  const [videoId, setVideoId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [runState, setRunState] = useState<RunState | null>(null);
  const latestServerState = useRef<RunState|null>(null);
  const [connectionIssue,setConnectionIssue] = useState(false);
  const pausedViewRef = useRef(false);
  const [report, setReport] = useState<ReportData | null>(initialReport || null);
  const [provisionalVerdict, setProvisionalVerdict] = useState<ProvisionalVerdict | null>(null);

  // Persisted events and live graph state
  const [events, setEvents] = useState<SimulationEvent[]>([]);
  const [isGraphPaused, setIsGraphPaused] = useState<boolean>(false);
  useEffect(()=>{pausedViewRef.current=isGraphPaused;},[isGraphPaused]);
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
          setTimeout(pollDel, 1000);
        }
      }
    };

    setTimeout(pollDel, 1000);
  };

  // Explicit new-upload intent never restores a prior run. Legacy /app and
  // owned run links retain durable recovery. Fence bootstrap against a new upload.
  useEffect(() => {
    let mounted=true;
    const bootstrapFence=runFenceRef.current;
    const current=()=>mounted && runFenceRef.current===bootstrapFence;
    initializeSession()
      .then(async data=>{
        if(!current())return;
        setSession(data);
        if(!startFresh && !requestedRunId){
          try{
            const dels=await listDeletions();
            if(!current())return;
            const pending=dels.find(d=>d.state?.status==='pending');
            if(pending){setDeletionState(pending.state);setViewState('deleting');startPollingDeletion(pending.id);return;}
          }catch{}
        }
        try{
          const vids=await listVideos();
          if(!current())return;
          setSavedVideos(vids);
          if(startFresh)return;
          const selected=requestedRunId?vids.find(v=>v.run_id===requestedRunId):vids[0];
          if(!selected){
            if(requestedRunId){setErrorMessage('saved_scan_unavailable');setViewState('error');}
            return;
          }
          setVideoId(selected.id);
          try{
            const analysis=await fetchAnalysis(selected.id);
            if(!current())return;
            if(analysis.available_profiles){
              setAvailableProfiles(analysis.available_profiles);
              if(!analysis.available_profiles.includes('flash'))setSelectedProfile('test');
            }
          }catch{}
          if(!current())return;
          if(selected.run_id){setRunId(selected.run_id);setViewState('processing');}
          else{setErrorMessage('Uploaded video found without an active run.');setViewState('error');}
        }catch{}
      })
      .catch(err=>{if(current())setSessionError(err.message || 'Session initialization failed');});
    return ()=>{mounted=false;delFenceRef.current++;abortActiveRunTasks();};
  }, []);

  // Poll / SSE for run updates when processing with non-overlapping requests and generation fencing
  useEffect(() => {
    if (viewState !== 'processing' || !runId) return;

    let isMounted = true;
    const currentFence = ++runFenceRef.current;
    const abortCtrl = new AbortController();
    pollAbortControllerRef.current = abortCtrl;
    const activeRunId = runId;
    const acceptState=(state:RunState)=>{
      const previous=latestServerState.current;
      if(previous?.run_id===state.run_id && (state.sequence<previous.sequence || (state.status==='queued' && previous.status!=='queued')))return previous;
      latestServerState.current=state;
      setRunState(state);setConnectionIssue(false);
      if(state.provisional_verdict)setProvisionalVerdict(state.provisional_verdict);
      return state;
    };

    let pollTimeout: ReturnType<typeof setTimeout> | null = null;
    let isPollBusy = false;
    let eventSource: EventSource | null = null;

    // Helper: Drain terminal events from server before completing
    const drainTerminalEvents = async (lastSeq: number) => {
      if (!isMounted || runFenceRef.current !== currentFence) return;
      try {
        const res = await fetch(`/runs/${activeRunId}/events?after=${lastSeq}`, {
          signal: AbortSignal.any([abortCtrl.signal,AbortSignal.timeout(10000)]),
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
                if (parsed.type === 'verdict.provisional' && parsed.payload) {
                  setProvisionalVerdict(parsed.payload);
                }
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
        const fetched = await fetchRun(activeRunId, abortCtrl.signal);
        if (!isMounted || runFenceRef.current !== currentFence) return;
        const state=acceptState(fetched);
        if (state.provisional_verdict) {
          setProvisionalVerdict(state.provisional_verdict);
        }

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
        if(isMounted && !abortCtrl.signal.aborted)setConnectionIssue(true);
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
          if(parsed?.type==='run.snapshot' && parsed.payload?.state?.run_id===activeRunId){
            acceptState(parsed.payload.state);return;
          }
          if (parsed && parsed.event_id) {
            const evItem: SimulationEvent = {
              event_id: parsed.event_id,
              sequence: parsed.sequence,
              type: parsed.type,
              payload: parsed.payload || {},
              created_at: parsed.created_at,
            };

            if (evItem.type === 'verdict.provisional' && evItem.payload) {
              setProvisionalVerdict(evItem.payload as any);
            }

            if (pausedViewRef.current) {
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
      eventSource.addEventListener('verdict.provisional', handleEvent);
      eventSource.addEventListener('run.snapshot', handleEvent);
      eventSource.addEventListener('message', handleEvent);
    } catch {}

    return () => {
      isMounted = false;
      abortCtrl.abort();
      if (pollTimeout) clearTimeout(pollTimeout);
      if (eventSource) eventSource.close();
    };
  }, [viewState, runId]);

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
    const uploadFence=runFenceRef.current;
    const current=()=>runFenceRef.current===uploadFence;
    let currentSession = session;
    if (!currentSession) {
      try {
        currentSession = await initializeSession();
        if(!current())return;
        setSession(currentSession);
      } catch (err: any) {
        if(!current())return;
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
      if(!current())return;
      setVideoId(up.video_id);

      // Check available profiles for uploaded media
      let profileToUse = selectedProfile;
      try {
        const analysis = await fetchAnalysis(up.video_id);
        if(!current())return;
        if (analysis.available_profiles) {
          setAvailableProfiles(analysis.available_profiles);
          // If user picked flash but this video only supports test (e.g. Video B)
          if (profileToUse === 'flash' && !analysis.available_profiles.includes('flash')) {
            // Respect truthful capability
            profileToUse = 'flash'; // Keep requested so backend returns explicit 422 if unhandled, or handle below
          }
        }
      } catch {}
      if(!current())return;

      setStatusMessage(`Video accepted. Queueing ${profileToUse === 'flash' ? '50-persona Flash' : '3-persona test'} analysis...`);

      const run = await startRun(up.video_id, currentSession.csrf, profileToUse);
      if(!current())return;
      setRunId(run.run_id);
      setProvisionalVerdict(null);
      setViewState('processing');
      onRunStarted?.(run.run_id);
    } catch (err: any) {
      if(!current())return;
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
    setProvisionalVerdict(null);
    setSelectedNote(null);
    setSelectedEvidence(null);
    setEvents([]);
    bufferedEventsRef.current = [];
    setIsGraphPaused(false);
    setDeletionState(null);
    setErrorMessage(null);
    setAvailableProfiles(['flash','test']);
    setViewState('idle');
    onNewUpload?.();
  };

  const effectiveMode=report?.trust?.mode || runState?.manifest?.provider_mode || session?.provider_mode || 'recorded';

  return (
    <div>
      {/* 56px utility header with responsive wrap at 320px */}
      <header className="app-header">
        <div className="brand-group">
          <Brand/>
          {effectiveMode === 'standard' ? (
            <span className="badge-recorded" style={{ background: '#2e1065', borderColor: '#7c3aed', color: '#e9d5ff' }}>
              your private screening room
            </span>
          ) : (
            <span className="badge-recorded">{effectiveMode==='recorded'?'recorded example':'design preview'}</span>
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

      <main className="app-main" id="main-content">
        <nav className="app-stepper" aria-label="Scan steps"><span aria-current={viewState==='idle'||viewState==='uploading'?'step':undefined}>01 / drop a video</span><span aria-current={viewState==='processing'?'step':undefined}>02 / meet your mobbs</span><span aria-current={viewState==='ready'?'step':undefined}>03 / director’s notes</span></nav>
        {sessionError && (
          <div className="alert-box error" role="alert">
            <strong>Session error:</strong> {sessionError}
          </div>
        )}

        {/* View 1: Upload Landing Desk */}
        {viewState === 'idle' && (
          <div className="upload-container">
            <h1 className="hero-heading">what are we watching?</h1>
            <p className="hero-subtitle">
              give your next cut a small, simulated crowd before you post it.
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
                <Doodle name="upload"/>
                <span>drop your video here</span>
                <small>or click to upload</small>
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

            {/* Profile Selection */}
            <div className="profile-selector-box" role="group" aria-label="Audience simulation profile">
              <span className="selector-title">choose your crowd</span>
              <div className="profile-options">
                <button
                  type="button"
                  className={`btn-toggle ${selectedProfile === 'flash' ? 'active' : ''}`}
                  onClick={() => setSelectedProfile('flash')}
                  aria-pressed={selectedProfile === 'flash'}
                >
                  <span className="btn-toggle-title">Flash · 50 mobbs</span>
                  <span className="btn-toggle-desc">the full crowd · more perspectives</span>
                </button>
                <button
                  type="button"
                  className={`btn-toggle ${selectedProfile === 'test' ? 'active' : ''}`}
                  onClick={() => setSelectedProfile('test')}
                  aria-pressed={selectedProfile === 'test'}
                >
                  <span className="btn-toggle-title">Quick preview · 3 mobbs</span>
                  <span className="btn-toggle-desc">a smaller crowd · a quicker first look</span>
                </button>
              </div>
            </div>

            <details className="disclosure-box">
              <summary>before you upload / privacy + simulation details</summary>
              <ul className="disclosure-list">
                <li>Upload an MP4 up to 60 seconds. We check it before the scan starts.</li>
                <li>Flash uses 50 fictional viewers; Quick preview uses 3. Their reactions are simulated, not real audience feedback.</li>
                {effectiveMode === 'standard' ? (
                  <li>Your video is processed by Meta Spark and Muse Voice Transcribe when audio is present. The mobbs watch scene by scene. Results are not predictions of real views.</li>
                ) : (
                  <li>Exact hash-bound recorded inference; no new provider latency or spend claimed.</li>
                )}
                <li>All uploaded video files, derivatives, and reports can be deleted at any time with access revoked immediately.</li>
              </ul>
            </details>
            {savedVideos.some(video=>video.run_id) && <details className="disclosure-box recent-scans">
              <summary>previous scans ({savedVideos.filter(video=>video.run_id).length})</summary>
              <ul className="disclosure-list">{savedVideos.filter(video=>video.run_id).map((video,index)=><li key={video.id}>
                <a href={`#/app/run/${encodeURIComponent(video.run_id!)}`}>previous scan {index+1}{video.metadata?.duration_ms?` · ${(video.metadata.duration_ms/1000).toFixed(1)}s`:''}</a>
              </li>)}</ul>
            </details>}
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

        {viewState === 'processing' && <>
          <ScanExperience state={runState} events={events} verdict={provisionalVerdict} videoId={videoId} paused={isGraphPaused} onPause={handleTogglePauseGraph} connectionIssue={connectionIssue}/>
          <div className="scan-cancel"><button className="text-button" type="button" onClick={e=>{triggerRef.current=e.currentTarget;setShowDeleteModal(true);}}>cancel scan & delete video</button></div>
        </>}

        {viewState === 'ready' && report && <ProductReport report={report} videoId={videoId} videoRef={videoRef} selectedNote={selectedNote} selectedEvidence={selectedEvidence} onNote={handleSelectNote} onEvidence={handleSelectEvidence} onCloseEvidence={()=>setSelectedEvidence(null)} onNew={handleReset} onDelete={e=>{triggerRef.current=e.currentTarget;setShowDeleteModal(true);}}/>}

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
        {viewState === 'error' && (() => {
          const formatted = formatRunErrorMessage(errorMessage);
          return (
            <div className="running-container">
              <span className="stage-badge" style={{ background: 'var(--error-tint)', color: 'var(--error)' }}>
                Analysis error
              </span>
              <h2>{formatted.title}</h2>
              <p style={{ color: 'var(--ink)', marginTop: '8px', maxWidth: '560px' }}>
                {formatted.explanation}
              </p>
              <p style={{ color: 'var(--muted)', marginTop: '6px', fontSize: '14px', maxWidth: '560px' }}>
                {formatted.guidance}
              </p>
              {errorMessage && (
                <div style={{ marginTop: '12px' }}>
                  <span className="badge" style={{ fontSize: '12px', background: 'var(--paper-dark)', color: 'var(--muted)' }}>
                    Diagnostic code: {errorMessage}
                  </span>
                </div>
              )}
              <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
                <button type="button" className="btn btn-primary" onClick={handleReset}>
                  Return to upload
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
          );
        })()}
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

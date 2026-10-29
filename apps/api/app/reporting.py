"""Report aggregation, resampling math, retention tables, and score indices."""
import math
import random
from contracts.normalized import (
    cast_status,
    content_hash,
    normalize_note,
    stop_trigger,
)
from .domain import utc


def build_report(manifest, video, checkpoints, rows, provider, source_sha, note_envelope, receipts):
    reactions = [r['reaction'] for r in rows]
    evidence_by_id = {r['evidence']['id']: r['evidence'] for r in rows}

    # Group reactions and checkpoints by persona
    checkpoints_by_pid = {c['persona_id']: c for c in checkpoints}
    reactions_by_pid = {}
    for r in reactions:
        reactions_by_pid.setdefault(r['persona_id'], []).append(r)

    # 1. Cast calculations
    requested = manifest['requested']
    counts = {
        status: sum(c['status'] == status for c in checkpoints)
        for status in ('complete', 'stopped', 'failed', 'active')
    }
    effective = counts['complete'] + counts['stopped']
    cast = dict(
        profile=manifest['profile'],
        requested=requested,
        effective=effective,
        failed=counts['failed'],
        pending=counts['active'],
        stopped=counts['stopped'],
    )
    cast['status'] = cast_status(manifest['profile'], requested, effective, cast['failed'], cast['pending'])

    # 2. Build whole persona traces for effective personas
    valid_pids = [c['persona_id'] for c in checkpoints if c['status'] in ('stopped', 'complete')]
    traces = {}
    for pid in valid_pids:
        p_reactions = sorted(reactions_by_pid.get(pid, []), key=lambda x: x['scene_id'])
        stopped_scene = None
        actions = set()
        for rx in p_reactions:
            if not rx['still_watching'] and stopped_scene is None:
                stopped_scene = rx['scene_id']
            for act in rx.get('actions', []):
                act_type = act['type'] if isinstance(act, dict) else act
                actions.add(act_type)
        traces[pid] = dict(
            persona_id=pid,
            status=checkpoints_by_pid[pid]['status'],
            reactions=p_reactions,
            stopped_scene=stopped_scene,
            actions=actions,
        )

    # 3. Scene setup for retention and score boundaries
    scenes = video['features']['scenes']
    duration_ms = video['metadata']['duration_ms']

    # Hook scene boundary: scene ending at min(3000ms, duration_ms)
    hook_boundary_ms = min(3000, duration_ms)
    hook_scene = next((s for s in scenes if s['end_ms'] >= hook_boundary_ms), scenes[0])
    hook_scene_id = hook_scene['scene_id']

    # Pacing scene boundary: scene representing 80% duration
    pacing_boundary_ms = 0.8 * duration_ms
    pacing_scene = next((s for s in scenes if s['end_ms'] >= pacing_boundary_ms), scenes[-1])
    pacing_scene_id = pacing_scene['scene_id']

    # 4. 200 Whole-persona trace resamples with replacement
    seed = manifest.get('resample_seed', 20261028)
    rng = random.Random(seed)

    survival_samples = {s['scene_id']: [] for s in scenes}
    drop_rate_samples = {s['scene_id']: [] for s in scenes}
    action_samples = {act: [] for act in ('like', 'share', 'save', 'comment')}
    hook_samples = []
    pacing_samples = []
    completion_samples = []

    if effective > 0:
        for _ in range(200):
            sample_pids = [rng.choice(valid_pids) for _ in range(effective)]
            sample_traces = [traces[p] for p in sample_pids]

            # Scene retention in this resample
            for s in scenes:
                sid = s['scene_id']
                entrants = sum(t['stopped_scene'] is None or t['stopped_scene'] >= sid for t in sample_traces)
                stopped = sum(t['stopped_scene'] == sid for t in sample_traces)
                continued = entrants - stopped
                survival_pct = (continued / effective) * 100.0
                survival_samples[sid].append(survival_pct)
                if entrants > 0:
                    drop_rate_samples[sid].append((stopped / entrants) * 100.0)
                else:
                    drop_rate_samples[sid].append(None)

            # Actions in this resample
            for act in ('like', 'share', 'save', 'comment'):
                act_count = sum(act in t['actions'] for t in sample_traces)
                action_samples[act].append((act_count / effective) * 100.0)

            # Hook & Pacing in this resample
            hook_surv = sum(t['stopped_scene'] is None or t['stopped_scene'] > hook_scene_id for t in sample_traces)
            hook_samples.append((hook_surv / effective) * 100.0)

            pacing_surv = sum(t['stopped_scene'] is None or t['stopped_scene'] > pacing_scene_id for t in sample_traces)
            pacing_samples.append((pacing_surv / effective) * 100.0)

            # Overall completion (reached final scene and did not stop)
            comp_count = sum(t['status'] == 'complete' for t in sample_traces)
            completion_samples.append((comp_count / effective) * 100.0)

    def compute_range(samples_list):
        non_null = [v for v in samples_list if v is not None]
        if not non_null:
            return None
        sorted_vals = sorted(non_null)
        idx10 = max(0, math.ceil(0.1 * len(non_null)) - 1)
        idx90 = min(len(sorted_vals) - 1, math.ceil(0.9 * len(non_null)) - 1)
        p10 = sorted_vals[idx10]
        p90 = sorted_vals[idx90]
        return dict(
            low=p10,
            high=p90,
            method=f'nearest-rank p10–p90; 200 whole-persona resamples; seed {seed}',
        )

    # 5. Build retention table
    retention = []
    for s in scenes:
        sid = s['scene_id']
        entrants = sum(t['stopped_scene'] is None or t['stopped_scene'] >= sid for t in traces.values())
        stopped = sum(t['stopped_scene'] == sid for t in traces.values())
        continued = entrants - stopped

        scene_evidence_ids = [r['evidence_id'] for r in reactions if r['scene_id'] == sid]

        surv_observed = (continued / effective * 100.0) if effective > 0 else None
        surv_range = compute_range(survival_samples[sid]) if effective > 0 else None
        survival_metric = dict(
            kind='simulation_range',
            unit='percent',
            observed=surv_observed,
            denominator=effective,
            range=surv_range,
            evidence_ids=scene_evidence_ids,
        )

        if entrants > 0:
            drop_observed = (stopped / entrants) * 100.0
            drop_range = compute_range(drop_rate_samples[sid])
            drop_metric = dict(
                kind='simulation_range',
                unit='percent',
                observed=drop_observed,
                denominator=entrants,
                range=drop_range,
                evidence_ids=[r['evidence_id'] for r in reactions if r['scene_id'] == sid and not r['still_watching']],
            )
        else:
            drop_metric = dict(
                kind='simulation_range',
                unit='percent',
                observed=None,
                denominator=0,
                range=None,
                evidence_ids=[],
                unavailable_reason='no_scene_entrants',
            )

        retention.append(dict(
            scene_id=sid,
            start_ms=s['start_ms'],
            end_ms=s['end_ms'],
            entrants=entrants,
            stopped=stopped,
            continued=continued,
            survival=survival_metric,
            drop_rate=drop_metric,
        ))

    # 6. Engagement metrics
    engagement = {}
    for act in ('like', 'share', 'save', 'comment'):
        act_pids = {pid for pid, t in traces.items() if act in t['actions']}
        act_ev_ids = [
            r['evidence_id']
            for r in reactions
            if any((a['type'] if isinstance(a, dict) else a) == act for a in r.get('actions', []))
        ]
        obs = (len(act_pids) / effective * 100.0) if effective > 0 else None
        engagement[act] = dict(
            kind='observed_rate',
            unit='percent',
            observed=obs,
            denominator=effective,
            range=compute_range(action_samples[act]) if effective > 0 else None,
            evidence_ids=act_ev_ids,
        )

    engagement['follow'] = dict(
        kind='observed_rate',
        unit='percent',
        observed=None,
        denominator=effective,
        range=None,
        evidence_ids=[],
        unavailable_reason='action_not_observed_by_legacy_provider',
    )

    # 7. Scores
    hook_ev_ids = [r['evidence_id'] for r in reactions if r['scene_id'] == hook_scene_id]
    hook_obs = (sum(t['stopped_scene'] is None or t['stopped_scene'] > hook_scene_id for t in traces.values()) / effective * 100.0) if effective > 0 else None
    hook_metric = dict(
        kind='heuristic_index',
        unit='percent',
        observed=hook_obs,
        denominator=effective,
        range=compute_range(hook_samples) if effective > 0 else None,
        evidence_ids=hook_ev_ids,
    )

    pacing_ev_ids = [r['evidence_id'] for r in reactions if r['scene_id'] == pacing_scene_id]
    pacing_obs = (sum(t['stopped_scene'] is None or t['stopped_scene'] > pacing_scene_id for t in traces.values()) / effective * 100.0) if effective > 0 else None
    pacing_metric = dict(
        kind='heuristic_index',
        unit='percent',
        observed=pacing_obs,
        denominator=effective,
        range=compute_range(pacing_samples) if effective > 0 else None,
        evidence_ids=pacing_ev_ids,
    )

    scores = dict(
        hook=hook_metric,
        pacing=pacing_metric,
        clarity=dict(
            kind='heuristic_index',
            unit='percent',
            observed=None,
            denominator=effective,
            range=None,
            evidence_ids=[],
            unavailable_reason='confusion_signal_unobserved',
        ),
        cta=dict(
            kind='heuristic_index',
            unit='percent',
            observed=None,
            denominator=None,
            range=None,
            evidence_ids=[],
            unavailable_reason='cta_understanding_signal_unobserved',
        ),
        trend=dict(
            kind='heuristic_index',
            unit='percent',
            observed=None,
            denominator=None,
            range=None,
            evidence_ids=[],
            unavailable_reason='grounded_trend_rules_unavailable',
        ),
    )

    # 8. Completion metric
    completed_pids = {c['persona_id'] for c in checkpoints if c['status'] == 'complete'}
    comp_obs = (len(completed_pids) / effective * 100.0) if effective > 0 else None
    completion = dict(
        kind='simulation_range',
        unit='percent',
        observed=comp_obs,
        denominator=effective,
        range=compute_range(completion_samples) if effective > 0 else None,
        evidence_ids=list(evidence_by_id),
    )

    # 9. Notes & Observations
    observations, notes, suppressed = [], [], 0
    for scene in scenes:
        trigger = stop_trigger(
            f"stop_{scene['scene_id']}",
            scene['scene_id'],
            scene['start_ms'],
            scene['end_ms'],
            reactions,
        )
        if trigger:
            observations.append(trigger)

    obs_by_id = {t['id']: t for t in observations}

    note_items = note_envelope['output'].get('notes', []) if isinstance(note_envelope.get('output'), dict) else []
    for i, item in enumerate(note_items):
        try:
            candidates = [
                t for t in observations
                if t['start_ms'] <= item['start_sec'] * 1000 < item['end_sec'] * 1000 <= t['end_ms']
            ]
            normalized = normalize_note(item, evidence_by_id, candidates[0] if candidates else None, f'n{i}')
            notes.append(normalized)
        except (ValueError, KeyError, TypeError, IndexError):
            suppressed += 1

    # Rank validated notes by trigger stop fraction descending, then start_ms ascending
    notes.sort(key=lambda n: (-obs_by_id.get(n.get('trigger_id'), {}).get('value', 0.0), n['start_ms']))

    # 10. Trust & Provenance
    if provider is not None:
        trust = provider.provenance()
        cast_ids = provider.persona_ids
    else:
        trust = dict(
            mode='synthetic',
            model_ids=['NO_MODEL_CALLED'],
            reported_versions=[None],
            media_sha256=content_hash(video.get('metadata', {})),
            limitations=['synthetic_fixture_not_provider_evidence'],
        )
        cast_ids = manifest.get('persona_ids', [])
    trust.update(
        app_source_sha=source_sha,
        observed_at=utc(),
        feature_sha256=content_hash(video['features']),
        cast_sha256=content_hash(cast_ids),
        config_sha256=content_hash({'profile': manifest['profile'], 'mode': manifest['provider_mode']}),
        prompt_sha256=content_hash({'projection': 'current-frame-and-own-prior-v02'}),
        usage_ledger=receipts,
    )

    methodology = dict(
        range_kind='simulation_resampling_not_confidence',
        ranking='heuristic stop fraction',
        assumptions=[
            'Independent simulated traces; not real viewers.',
            'Internal cast variability omits model bias and real audience mismatch.',
            f'Hook score is survival after the scene covering 3s (scene {hook_scene_id}, {hook_scene["end_ms"]}ms).',
            f'Pacing score is survival after the scene covering 80% duration (scene {pacing_scene_id}, {pacing_scene["end_ms"]}ms under scene-boundary timing).',
            'Coarse scene-boundary decisions are recorded at segment ends.',
        ],
    )

    caveats = list(video['features'].get('caveats', [])) + [
        f'{suppressed} unsupported note(s) suppressed.',
        'Signals for confusion, CTA understanding and trend fit unavailable.',
        'Action follow not observed in legacy responses.',
        'No causal, virality, reach or audience calibration claim.',
    ]

    return dict(
        schema_version='normalized-1',
        manifest=manifest,
        cast=cast,
        retention=retention,
        engagement=engagement,
        scores=scores,
        completion=completion,
        notes=notes[:3],
        observations=observations,
        evidence=list(evidence_by_id.values()),
        trust=trust,
        duration_ms=duration_ms,
        scenes=scenes,
        suppressed_notes=suppressed,
        methodology=methodology,
        caveats=caveats,
        coverage=dict(transcript=False, ocr=False, confused=None, cta_understood=None, trend_fit=None),
    )

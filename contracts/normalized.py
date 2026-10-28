"""Content-only conversion. No network, tool execution, or provider SDK dependency.

All times use decimal half-up rounding to integer milliseconds. Unknown action
times stay null. This module is the production boundary for the future V02 app;
the historical experiment is deliberately unchanged.
"""
import json
import hashlib
import math
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

ACTIONS = frozenset(('like', 'share', 'save', 'comment', 'follow'))
LEGACY_ACTIONS = ACTIONS - {'follow'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'invalid integer')
    return value


def text(value, limit=2000):
    require(isinstance(value, str) and 0 < len(value.strip()) <= limit, 'invalid string')
    return value


def milliseconds(seconds):
    require(type(seconds) in (int, float) and math.isfinite(seconds) and seconds >= 0,
            'invalid seconds')
    return int((Decimal(str(seconds)) * 1000).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def parse_json(value):
    def invalid(_):
        raise ValueError('nonfinite JSON number')
    def pairs(items):
        result = {}
        for key, item in items:
            require(key not in result, 'duplicate JSON field')
            result[key] = item
        return result
    def finite_float(value):
        number = float(value)
        require(math.isfinite(number), 'nonfinite JSON number')
        return number
    return json.loads(value, parse_constant=invalid, parse_float=finite_float, object_pairs_hook=pairs)


def normalize_envelope(raw, receipt):
    """Join saved response with Client.call ledger, retaining usage on failure.

    HTTP errors have no saved body in Client.call; raw may be None only there.
    Never return raw provider error prose, refusal prose, or reasoning content.
    """
    status_code = integer(receipt['http_status'], 100)
    latency = receipt['latency_sec']
    result = dict(request_id=receipt.get('request_id'),
                  model_id=(raw or {}).get('model') or receipt.get('requested_model'),
                  reported_version=None, output=None, usage=None,
                  latency_ms=milliseconds(latency), status=None,
                  response_id=(raw or {}).get('id'), error=None,
                  incomplete_reason=None, cancellation='unknown')
    if status_code >= 400:
        result.update(status='error', error={'code': 'provider_http_error',
                      'http_status': status_code, 'charge_state': 'uncertain' if status_code >= 500 else 'unconfirmed'})
        return result
    require(isinstance(raw, dict), 'missing successful response body')
    usage = raw.get('usage')
    if usage is not None:
        result['usage'] = {k: integer(usage[k]) for k in ('input_tokens', 'output_tokens', 'total_tokens')}
        require(usage['total_tokens'] == usage['input_tokens'] + usage['output_tokens'], 'inconsistent usage')
        for parent, key in [('input_tokens_details', 'cached_tokens'), ('output_tokens_details', 'reasoning_tokens')]:
            result['usage'][key] = integer(usage[parent][key]) if key in (usage.get(parent) or {}) else None
        require(result['usage']['cached_tokens'] is None or result['usage']['cached_tokens'] <= usage['input_tokens'], 'bad cached usage')
        require(result['usage']['reasoning_tokens'] is None or result['usage']['reasoning_tokens'] <= usage['output_tokens'], 'bad reasoning usage')
    status = raw.get('status')
    require(status in ('completed', 'incomplete', 'failed'), 'unsupported response status')
    if status == 'incomplete':
        reason = (raw.get('incomplete_details') or {}).get('reason')
        result.update(status='incomplete', incomplete_reason=reason if reason == 'max_output_tokens' else 'unknown')
        return result
    if status == 'failed' or raw.get('error') is not None:
        result.update(status='error', error={'code': 'provider_response_error', 'charge_state': 'unconfirmed'})
        return result
    pieces = []
    for item in raw.get('output', []):
        require(item.get('type') in ('message', 'reasoning'), 'unexpected output type')
        if item['type'] == 'message':
            for content in item.get('content', []):
                if content.get('type') == 'refusal':
                    result['status'] = 'refused'
                    return result
                require(content.get('type') == 'output_text', 'unexpected message content')
                pieces.append(content['text'])
    require(pieces, 'missing structured output')
    result.update(status='completed', output=parse_json(''.join(pieces)))
    return result


def validate_reaction(value, persona_ids, scenes):
    require(value['persona_id'] in persona_ids, 'unknown persona')
    require(type(value['scene_id']) is int and value['scene_id'] in scenes, 'unknown scene')
    start, end = scenes[value['scene_id']]
    integer(start); integer(end); require(start < end, 'invalid scene')
    require(type(value['still_watching']) is bool, 'invalid watching flag')
    require(len(text(value['impression_update']).split()) <= 60, 'oversized impression')
    if value['still_watching']:
        require(value['drop_reason'] is None, 'continued viewer has drop reason')
    else:
        text(value['drop_reason'])
    seen = set()
    require(isinstance(value['actions'], list), 'invalid actions')
    for action in value['actions']:
        require(action['type'] in ACTIONS and action['type'] not in seen, 'unknown/duplicate action')
        seen.add(action['type'])
        at = action['at_ms']
        require(at is None or (type(at) is int and start <= at < end), 'invalid action time')
        require((at is None) == (action['timing'] == 'unobserved'), 'invalid action timing semantics')
        require(action['timing'] in ('unobserved', 'observed'), 'unknown timing')
    signals = value['signals']
    require(all(signals[k] is None or type(signals[k]) is bool for k in ('confused', 'cta_understood')), 'invalid signal')
    require(signals['matched_trend_rule_ids'] == [], 'trend evidence unavailable in v1 conversion')
    text(value['evidence_id'])
    return value


def normalize_verdict(raw, persona_id, scene_id, start_sec, end_sec, evidence_id):
    values = raw.get('verdicts')
    require(isinstance(values, list) and len(values) == 1, 'wrong verdict count')
    item = values[0]
    require(item['persona_id'] == persona_id, 'wrong persona')
    reason = text(item['reason'])
    require(len(text(item['impression']).split()) <= 30, 'legacy impression exceeds 30 words')
    require(isinstance(item['actions'], list) and all(a in LEGACY_ACTIONS for a in item['actions']), 'unknown legacy action')
    start, end = milliseconds(start_sec), milliseconds(end_sec)
    reaction = dict(persona_id=persona_id, scene_id=scene_id, still_watching=item['still_watching'],
                    actions=[dict(type=a, at_ms=None, timing='unobserved') for a in item['actions']],
                    impression_update=item['impression'], drop_reason=None if item['still_watching'] else reason,
                    signals=dict(confused=None, cta_understood=None, matched_trend_rule_ids=[]), evidence_id=evidence_id)
    validate_reaction(reaction, {persona_id}, {scene_id: (start, end)})
    evidence = dict(id=evidence_id, persona_id=persona_id, scene_id=scene_id,
                    start_ms=start, end_ms=end, quote=reason, kind='simulated_reason',
                    still_watching=item['still_watching'])
    return reaction, evidence


def stop_trigger(trigger_id, scene_id, start_ms, end_ms, reactions):
    """Deterministic V02 supported detector: >=15% stop among scene entrants."""
    integer(start_ms); integer(end_ms); require(start_ms < end_ms, 'invalid trigger range')
    selected = [r for r in reactions if r['scene_id'] == scene_id]
    require(len({r['persona_id'] for r in selected}) == len(selected), 'duplicate scene respondent')
    stopped = [r for r in selected if r['still_watching'] is False]
    if not selected or len(stopped) / len(selected) < .15:
        return None
    return dict(id=trigger_id, scene_id=scene_id, start_ms=start_ms, end_ms=end_ms,
                kind='stop_fraction', numerator=len(stopped), denominator=len(selected),
                value=len(stopped)/len(selected), threshold=.15,
                evidence_refs=[r['evidence_id'] for r in stopped])


def normalize_note(item, evidence, trigger, note_id):
    """Map exact legacy quotes and seconds only when a deterministic trigger exists."""
    require(trigger is not None and trigger['kind'] == 'stop_fraction', 'unsupported trigger')
    refs = item['evidence_ids']
    require(isinstance(refs, list) and refs and len(set(refs)) == len(refs) and set(refs) <= set(evidence), 'bad evidence references')
    selected = [evidence[k] for k in refs]
    require(set(trigger['evidence_refs']) & set(refs), 'note does not cite trigger')
    quotes = item['quotes']
    require(isinstance(quotes, list) and quotes and all(q in {e['quote'] for e in selected} for q in quotes), 'unmatched quote')
    start, end = milliseconds(item['start_sec']), milliseconds(item['end_sec'])
    require(trigger['start_ms'] <= start < end <= trigger['end_ms'], 'note outside trigger')
    require(any(e['start_ms'] <= start < end <= e['end_ms'] for e in selected), 'unsupported note time')
    fix = text(item['suggested_edit'])
    for clause in re.split(r'[.;:]', fix):
        for match in re.finditer(r'(?:synthetic|fake|invented|fabricated|mock(?:ed|up)?)\s+(?:product\s+)?(?:ui|interface|demo|proof|testimonial)', clause, re.I):
            require(re.search(r"\b(?:do not|don't|never|avoid|without)\b[^.;:]*$", clause[:match.start()], re.I), 'fabricated proof suggestion')
    return dict(id=note_id, start_ms=start, end_ms=end, trigger_id=trigger['id'],
                interpretation=text(item['finding']), fix=fix, evidence_refs=refs,
                quotes=[dict(evidence_id=next(e['id'] for e in selected if e['quote'] == q), text=q) for q in quotes],
                status='open', ranking_method='heuristic')


def cast_status(profile, requested, effective, failed, pending):
    for value in (requested, effective, failed, pending): integer(value)
    require(requested > 0 and effective + failed + pending == requested, 'inconsistent cast')
    require(profile in ('test', 'flash') and (profile != 'flash' or requested == 50), 'unknown/invalid profile')
    if pending: return 'processing'
    if effective == 0: return 'failed'
    if effective < requested: return 'incomplete'
    return 'complete_test_profile' if profile == 'test' else 'complete'


def timestamp(value):
    require(isinstance(value, str) and value.endswith('Z'), 'UTC timestamp required')
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def validate_deletion(value):
    revoked = timestamp(value['access_revoked_at'])
    require(value['access_revoked'] is True, 'access must be revoked')
    require(value['repeat_deletion_id'] == value['deletion_id'], 'repeat created new deletion')
    integer(value['fence_generation'], 1)
    targets = value['targets']
    require(set(targets) == {'originals', 'derivatives', 'provider_files', 'runs', 'events', 'reports', 'jobs'}, 'incomplete inventory')
    pending = []
    for key, target in targets.items():
        require(target['status'] in ('pending', 'failed', 'complete'), 'unknown deletion target state')
        integer(target['attempts'])
        if target['status'] == 'complete':
            require(timestamp(target['completed_at']) >= revoked, 'completion precedes revoke')
            require(target['retry_at'] is None and target['error_code'] is None, 'completed retry/error')
        else:
            pending.append(key)
            require(target['completed_at'] is None, 'pending target completed time')
            if target['status'] == 'failed':
                text(target['error_code']); require(timestamp(target['retry_at']) >= revoked, 'invalid retry')
    complete = not pending
    require(value['pending_targets'] == sorted(pending), 'pending inventory mismatch')
    require(value['can_claim_complete'] is complete, 'false complete claim')
    require(value['status'] == ('complete' if complete else 'pending'), 'bad deletion status')
    require((value['completed_at'] is not None) is complete, 'bad operation completion time')
    if complete:
        require(timestamp(value['completed_at']) >= max(timestamp(t['completed_at']) for t in targets.values()), 'early completion')
    return value


def may_publish_job(lease_generation, current_generation, deleted):
    integer(lease_generation); integer(current_generation)
    require(type(deleted) is bool, 'invalid tombstone')
    return not deleted and lease_generation == current_generation


def content_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_event(value):
    text(value['run_id']); text(value['event_id']); integer(value['sequence'], 1)
    require(value['type'] in ('persona.stopped', 'persona.continued', 'run.snapshot', 'deletion.pending', 'deletion.complete'), 'unknown event type')
    payload = value['payload']
    if value['type'].startswith('persona.'):
        text(payload['persona_id']); integer(payload['scene_id']); integer(payload['at_ms']); text(payload['evidence_id'])
    elif value['type'] == 'run.snapshot':
        integer(payload['through_sequence']); require(payload['reset'] is True, 'snapshot reset missing')
    else:
        text(payload['deletion_id'])
    return value


def validate_fixture(fixture):
    require(fixture['schema_version'] == 'normalized-1', 'unknown schema version')
    report = fixture['expected']
    trust = report['trust']
    require(fixture['provenance'] == 'SYNTHETIC_DESIGN_FIXTURE_NOT_PROVIDER_EVIDENCE' and trust['mode'] == 'synthetic', 'synthetic fixture claimed live')
    require(trust['source_sha'] is None and trust['source_sha_unavailable_reason'] == 'synthetic_not_executed', 'invented source revision')
    for key in ('media_sha256', 'feature_sha256', 'cast_sha256', 'config_sha256', 'prompt_sha256'):
        require(re.fullmatch('[0-9a-f]{64}', trust[key]) is not None, 'invalid hash')
    for field, source in [('feature_sha256', fixture['features']), ('cast_sha256', fixture['cast_definition']), ('config_sha256', fixture['config']), ('prompt_sha256', fixture['prompt_template'])]:
        require(trust[field] == content_hash(source), 'content hash mismatch')
    require(trust['media_sha256'] == fixture['media']['sha256'], 'media hash mismatch')
    timestamp(trust['observed_at'])
    require(trust['model_ids'] == ['NO_MODEL_CALLED'] and trust['usage_ledger'] == [], 'invented calls')
    require(trust['reported_versions'] == [None] and trust['limitations'], 'missing trust limitations')
    cast = report['cast']
    require(cast['status'] == cast_status(cast['profile'], cast['requested'], cast['effective'], cast['failed'], cast['pending']), 'wrong cast status')
    ids = {pid for b in fixture['batches'] for pid in b['persona_ids']}
    require(len(ids) == cast['requested'], 'requested cast mismatch')
    scenes = {s['scene_id']: (s['start_ms'], s['end_ms']) for s in fixture['features']['scenes']}
    ordered = fixture['features']['scenes']
    require(len(scenes) == len(ordered) and ordered[0]['start_ms'] == 0 and ordered[-1]['end_ms'] == fixture['media']['duration_ms'], 'scene coverage mismatch')
    require(ordered[0]['end_ms'] == min(3000, fixture['media']['duration_ms']), 'missing hook boundary')
    require(all(0 < s['end_ms']-s['start_ms'] <= 5000 for s in ordered), 'invalid scene duration')
    require(all(a['end_ms'] == b['start_ms'] for a, b in zip(ordered, ordered[1:])), 'noncontiguous scenes')
    evidence = {e['id']: e for e in report['evidence']}
    require(len(evidence) == len(report['evidence']), 'duplicate evidence')
    seen, stopped = set(), set()
    for r in fixture['verdicts']:
        validate_reaction(r, ids, scenes)
        key = (r['persona_id'], r['scene_id'])
        require(key not in seen and r['persona_id'] not in stopped, 'duplicate or post-skip reaction')
        seen.add(key)
        require(r['evidence_id'] in evidence, 'missing reaction evidence')
        e = evidence[r['evidence_id']]
        require((e['persona_id'], e['scene_id']) == key and (e['start_ms'], e['end_ms']) == scenes[r['scene_id']], 'wrong evidence identity/time')
        text(e['quote'])
        if not r['still_watching']:
            require(e['quote'] == r['drop_reason'], 'wrong stop quote'); stopped.add(r['persona_id'])
    terminal = stopped | {r['persona_id'] for r in fixture['verdicts'] if r['scene_id'] == ordered[-1]['scene_id']}
    require(cast['effective'] == len(terminal), 'effective cast mismatch')
    require(cast['stopped'] == len(stopped), 'stopped cast mismatch')
    for batch in fixture['batches']:
        require(batch['scene_id'] in scenes and batch['max_visible_ms'] == scenes[batch['scene_id']][1], 'bad batch visibility')
        for pid in batch['persona_ids']:
            require(not any(r['persona_id'] == pid and not r['still_watching'] and r['scene_id'] < batch['scene_id'] for r in fixture['verdicts']), 'post-skip batch')
    completed = [pid for pid in ids if any(r['persona_id'] == pid and r['scene_id'] == ordered[-1]['scene_id'] and r['still_watching'] for r in fixture['verdicts'])]
    require(report['completion_count'] == len(completed) and report['denominator'] == cast['effective'], 'bad completion count')
    indices = report['bootstrap_indices']
    cast_order = fixture['cast_definition']['persona_ids']
    require(len(set(cast_order)) == len(cast_order) and set(cast_order) == ids, 'bad cast definition')
    samples = []
    for sample in indices:
        require(len(sample) == len(cast_order) and all(type(i) is int and 0 <= i < len(cast_order) for i in sample), 'bad bootstrap index')
        samples.append(sum(cast_order[i] in completed for i in sample)/len(sample)*100)
    require(samples == report['completion_samples_percent'], 'bad sample arithmetic')
    metric = report['metric']
    require(metric['observed'] == len(completed)/cast['effective']*100, 'bad observed metric')
    require([metric['range']['low'], metric['range']['high']] == [sorted(samples)[math.ceil(p*len(samples))-1] for p in (.1, .9)], 'bad range')
    trigger = stop_trigger('fixture_hook_drop', 0, *scenes[0], fixture['verdicts'])
    require(report['observations'] == [trigger], 'invalid deterministic observation')
    n = report['note']
    converted = normalize_note(dict(start_sec=n['start_ms']/1000, end_sec=n['end_ms']/1000,
        evidence_ids=n['evidence_refs'], quotes=[q['text'] for q in n['quotes']], finding=n['interpretation'], suggested_edit=n['fix']), evidence, trigger, n['id'])
    require(n == converted, 'note does not match evidence/trigger')
    require(report['metric']['denominator'] == cast['effective'] and set(report['metric']['evidence_ids']) <= set(evidence), 'bad metric denominator/evidence')
    require(report['coverage']['signals_unavailable'] == ['confused', 'cta_understood', 'trend_fit'], 'missing coverage')
    require(report['methodology']['range_kind'] == 'simulation_resampling_not_confidence' and report['caveats'], 'missing method/caveats')
    validate_event(fixture['event_example'])
    for event in fixture['event_examples']: validate_event(event)
    for case in fixture['cast_examples']:
        require(case['status'] == cast_status(case['profile'], case['requested'], case['effective'], case['failed'], case['pending']), 'bad profile example')
    for case in fixture['stale_job_examples']:
        require(case['may_publish'] is may_publish_job(case['lease_generation'], case['current_generation'], case['deleted']), 'bad job fence example')
    validate_deletion(report['deletion'])
    for deletion in fixture['deletion_examples']: validate_deletion(deletion)
    return fixture

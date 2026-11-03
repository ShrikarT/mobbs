"""Read-only private evidence reconciliation; stdout contains hashes/counts only.

Run from repository root: python -m tests.reconcile_saved [--write]
--write refreshes only the sanitized committed projection, never the originals.
"""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from contracts.normalized import normalize_envelope, normalize_verdict, normalize_note, stop_trigger

ROOT = Path('C:/Users/Shrikar/.codex/private-runs/viralist-spark13-20261028')
DESTINATION = Path('docs/contracts/provider-saved.v1.json')


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def shape(value):
    if isinstance(value, dict): return {key: shape(item) for key, item in value.items()}
    if isinstance(value, list):
        unique = []
        for item in value:
            s = shape(item)
            if s not in unique: unique.append(s)
        return unique
    return type(value).__name__


def identifier(value):
    assert value is None or re.fullmatch(r'[A-Za-z0-9_-]{1,120}', value)
    return value


def extract():
    specs = [('success', 'stage1-bounded', 'response-040-a-3-s0-p002.json', 40),
             ('incomplete', 'stage1-final', 'response-035-b-3-s2-p002.json', 35),
             ('http_error', 'stage1-final', None, 16)]
    examples = []
    for kind, stage, name, number in specs:
        directory = ROOT / stage
        ledger_path = directory / 'ledger.json'
        ledger = load(ledger_path)
        call = next(c for c in ledger['calls'] if c['number'] == number)
        report_path = directory / ('gate.json' if stage == 'stage1-bounded' else 'pre-repair-report.json')
        revision = load(report_path)['source_sha']
        source_hashes = {name: hashlib.sha256(subprocess.check_output(['git', 'show', f'{revision}:{name}'])).hexdigest()
                         for name in ('experiments/meta_pipeline.py', 'experiments/meta_smoke.py')}
        raw = load(directory/name) if name else None
        if name:
            assert name == f"response-{number:03d}-{call['label']}.json"
            assert raw['id'] == call['response_id'] and raw['usage'] == call['usage']
        else:
            assert call['status'] == 'http_error' and call['http_status'] == 500
        receipt = {k: call.get(k) for k in ('http_status', 'request_id', 'requested_model', 'latency_sec')}
        receipt['request_id'] = identifier(receipt['request_id'])
        normalized = normalize_envelope(raw, receipt)
        original_shape = shape(normalized['output'])
        normalized['output'] = {} if normalized['output'] is not None else None
        sanitized_raw = None
        if raw:
            sanitized_raw = {k: raw.get(k) for k in ('model', 'status', 'usage', 'incomplete_details', 'error')}
            assert sanitized_raw['error'] is None
            sanitized_raw['id'] = identifier(raw['id'])
            sanitized_raw['output'] = []
            for block in raw['output']:
                if block['type'] == 'reasoning':
                    sanitized_raw['output'].append({'type': 'reasoning'})
                elif block['type'] == 'message':
                    assert all(c['type'] == 'output_text' for c in block['content'])
                    sanitized_raw['output'].append({'type': 'message', 'content': [{'type': 'output_text', 'text': '{}'}]})
                else: raise AssertionError('unrecognized output block')
        assert normalize_envelope(sanitized_raw, receipt) == normalized
        examples.append(dict(kind=kind, source_revision=revision, source_code_sha256=source_hashes,
            source_response_file=f'{stage}/{name}' if name else None,
            source_response_sha256=sha(directory/name) if name else None,
            source_ledger_file=f'{stage}/ledger.json', source_ledger_sha256=sha(ledger_path),
            source_revision_record=f'{stage}/{report_path.name}', source_revision_record_sha256=sha(report_path),
            ledger_call_number=number, ledger_status=call['status'], receipt=receipt,
            raw_projection=sanitized_raw, normalized=normalized, original_output_shape=original_shape,
            redaction='All private output text replaced by synthetic empty JSON; reasoning content and all non-allowlisted fields removed. HTTP error is ledger-only; no saved response body exists.' ))
    # Inspect all saved /responses for refusal discriminators, without copying prose.
    statuses, refusals = {}, 0
    for f in ROOT.glob('*/response-*.json'):
        raw = load(f)
        if 'output' not in raw: continue
        status = raw.get('status')
        statuses[status] = statuses.get(status, 0) + 1
        refusals += sum(c.get('type') == 'refusal' for o in raw['output'] for c in o.get('content', []))
    assert refusals == 0
    return dict(schema_version='saved-envelope-1', provenance='SANITIZED_SAVED_EVIDENCE_WITH_SYNTHETIC_TEXT_SUBSTITUTION',
                examples=examples, inspected_status_counts=statuses, refusal='unobserved',
                reported_version='unavailable_in_saved_envelopes', cancellation='unknown_not_exercised')


def check_conversion():
    counts = dict(reactions=0, supported_notes=0, suppressed_notes=0)
    stage = ROOT/'stage1-bounded'
    hashes = {}
    ledger = load(stage/'ledger.json')
    calls = {c['label']: c for c in ledger['calls']}
    def saved_output(label):
        call = calls[label]
        path = stage/f"response-{call['number']:03d}-{label}.json"
        raw = load(path)
        assert raw['usage'] == call['usage'] and raw['id'] == call['response_id']
        normalized = normalize_envelope(raw, call)
        assert normalized['status'] == 'completed'
        hashes[path.name] = sha(path)
        return normalized['output']
    for video in ('a', 'b'):
        path = stage/f'{video}-3-reactions.json'
        records = load(path)
        reactions, evidence = [], {}
        for row in records:
            original = saved_output(f"{video}-3-s{row['scene']}-{row['persona_id']}")
            for key in ('persona_id', 'still_watching', 'actions', 'reason', 'impression'):
                assert original['verdicts'][0][key] == row[key], 'saved reaction mismatch'
            reaction, e = normalize_verdict(original, row['persona_id'], row['scene'],
                row['start_sec'], row['end_sec'], row['evidence_id'])
            reactions.append(reaction); evidence[e['id']] = e
            counts['reactions'] += 1
        hashes[path.name] = sha(path)
        notes_path = stage/f'{video}-3-notes.json'
        hashes[notes_path.name] = sha(notes_path)
        assert saved_output(f'{video}-3-notes') == load(notes_path), 'saved note mismatch'
        for index, note in enumerate(load(notes_path)['notes']):
            selected = [evidence[k] for k in note['evidence_ids']]
            trigger = None
            for e in selected:
                trigger = stop_trigger('private_stop', e['scene_id'], e['start_ms'], e['end_ms'], reactions)
                if trigger: break
            if trigger is None:
                counts['suppressed_notes'] += 1
                continue
            normalize_note(note, evidence, trigger, f'n{index}')
            counts['supported_notes'] += 1
    return dict(counts=counts, private_artifact_sha256=hashes)


def main():
    result = extract()
    conversion = check_conversion()
    result['conversion_check'] = conversion
    if '--write' in sys.argv:
        DESTINATION.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    else:
        assert result == load(DESTINATION), 'saved projection/hash mismatch'
    print(json.dumps(dict(result='PASS', fixture_sha256=sha(DESTINATION), **conversion)))


if __name__ == '__main__': main()

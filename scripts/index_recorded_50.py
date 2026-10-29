"""Read-only 50-person evidence import index: hashes/IDs/ranges only, never model prose."""
import json
from pathlib import Path
from contracts.normalized import milliseconds, require
from apps.api.app.config import ROOT, settings
from apps.api.app.providers import digest


def build_index():
    ev_root = Path(settings().provider_evidence_root).resolve()
    if ev_root.name == 'stage1-bounded':
        stage2_root = ev_root.parent / 'stage2-bounded'
    elif (ev_root / 'stage2-bounded').is_dir():
        stage2_root = ev_root / 'stage2-bounded'
    else:
        stage2_root = ev_root

    # Verify canonical reactions and notes container hashes
    reactions_bytes = (stage2_root / 'a-50-reactions.json').read_bytes()
    notes_bytes = (stage2_root / 'a-50-notes.json').read_bytes()
    require(digest(reactions_bytes) == 'b055a1c4c6d058e47dc99102d208b4252b63682e9fe9b628951f0b80a39b155c', 'reactions hash mismatch')
    require(digest(notes_bytes) == '233fe9837cd0d4b7d98087f541c12b6d829b47097b0eaa3f8164ec38c6fcbd47', 'notes hash mismatch')

    # Verify original media A
    media = json.loads((stage2_root / 'media.json').read_text(encoding='utf-8-sig'))
    m_a = media['a']
    require(m_a['sha256'] == 'c76b510a43b6aaaf90dc152e8be358f0e6efb64a95ebc785c8cd51af7713975a', 'media A sha mismatch')
    orig_path = Path(m_a['path'])
    require(orig_path.is_file() and digest(orig_path.read_bytes()) == m_a['sha256'], 'orig file mismatch')

    # Verify all calls in ledger
    ledger = json.loads((stage2_root / 'ledger.json').read_bytes())
    calls = [c for c in ledger['calls'] if c['label'].startswith('a-50-s') or c['label'] == 'a-50-notes']
    require(len(calls) == 257, 'expected 257 calls, got ' + str(len(calls)))

    artifact_names = {'a-50-reactions.json', 'a-50-notes.json', 'media.json', 'ledger.json'}
    for extra in ('a-50-dispatch-audit.json', 'a-50-summary.json', 'verification.json'):
        if (stage2_root / extra).is_file():
            artifact_names.add(extra)

    for c in calls:
        fn = f"response-{c['number']:03d}-{c['label']}.json"
        data = (stage2_root / fn).read_bytes()
        raw = json.loads(data)
        require(raw['id'] == c['response_id'], 'response_id mismatch in ' + fn)
        require(raw['usage'] == c['usage'], 'usage mismatch in ' + fn)
        artifact_names.add(fn)

    raw_reactions = json.loads(reactions_bytes)
    pids = sorted({r['persona_id'] for r in raw_reactions})
    require(len(pids) == 50, 'expected 50 unique persona IDs, got ' + str(len(pids)))
    require(pids == [f'p{i:03d}' for i in range(1, 51)], 'persona IDs must be p001-p050')

    specs = [
        dict(
            name='a',
            sha256=m_a['sha256'],
            duration_ms=milliseconds(m_a['duration_sec']),
            persona_ids=pids,
            scenes=[
                dict(
                    scene_id=s['index'],
                    start_ms=milliseconds(s['start_sec']),
                    end_ms=milliseconds(s['end_sec']),
                )
                for s in m_a['scenes']
            ],
        )
    ]

    index = dict(
        profile='flash',
        source_sha='04b852728ae22967f408f71e34f274911ab07578',
        observed_at='2026-10-28',
        media=specs,
        artifact_sha256={n: digest((stage2_root / n).read_bytes()) for n in sorted(artifact_names)},
    )

    out_path = ROOT / 'apps/api/recorded-50-index.json'
    out_path.write_text(json.dumps(index, indent=2) + '\n')
    print(f'Indexed hash-verified private 50-person evidence: 1 media, {len(raw_reactions)} reactions, 50 terminal stops; no model text exported')
    return index


if __name__ == '__main__':
    build_index()

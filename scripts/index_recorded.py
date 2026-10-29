"""Read-only evidence import index: hashes/IDs/ranges only, never model prose."""
import json
from pathlib import Path
from contracts.normalized import milliseconds, require
from apps.api.app.config import ROOT, settings
from apps.api.app.providers import digest

root = Path(settings().provider_evidence_root)
if (root/'stage1-bounded').is_dir(): root /= 'stage1-bounded'
fixture = json.loads((ROOT/'docs/contracts/provider-saved.v1.json').read_text())
anchored = fixture['conversion_check']['private_artifact_sha256']
for name, sha in anchored.items():
    require(digest((root/name).read_bytes()) == sha, 'accepted evidence hash mismatch')
require(digest((root/'ledger.json').read_bytes()) == fixture['examples'][0]['source_ledger_sha256'], 'ledger mismatch')
require(digest((root/'gate.json').read_bytes()) == fixture['examples'][0]['source_revision_record_sha256'], 'gate mismatch')
media = json.loads((root/'media.json').read_text(encoding='utf-8-sig'))
specs = []
for name in ('a','b'):
    m = media[name]
    require(digest(Path(m['path']).read_bytes()) == m['sha256'], 'original media mismatch')
    rows = json.loads((root/f'{name}-3-reactions.json').read_text())
    specs.append(dict(name=name,sha256=m['sha256'],duration_ms=milliseconds(m['duration_sec']),
        persona_ids=sorted({r['persona_id'] for r in rows}),
        scenes=[dict(scene_id=s['index'],start_ms=milliseconds(s['start_sec']),end_ms=milliseconds(s['end_sec'])) for s in m['scenes']]))
names = set(anchored) | {'media.json','ledger.json','gate.json'}
index = dict(source_sha='04b852728ae22967f408f71e34f274911ab07578',
    observed_at='2026-10-28', media=specs,
    artifact_sha256={n:digest((root/n).read_bytes()) for n in sorted(names)})
(ROOT/'apps/api/recorded-index.json').write_text(json.dumps(index,indent=2)+'\n')
print('Indexed hash-verified private evidence: 2 media, 19 reactions; no model text exported')

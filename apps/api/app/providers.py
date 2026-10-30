"""Explicit Standard Meta boundary; local V02 permits only hash-bound recorded inputs."""
import hashlib
import json
from pathlib import Path
from contracts.normalized import normalize_envelope, normalize_verdict, require, milliseconds
from .config import ROOT, settings


class ProviderUnavailable(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


class MetaStandardAdapter:
    mode = 'standard'
    model_id = 'muse-spark-1.3'

    def infer(self, scene_input):
        # Fail closed before reading any API credentials or constructing a network client.
        # A future live implementation needs explicit authority plus durable budget reservations.
        raise ProviderUnavailable('fresh_provider_authorization_required')

    @staticmethod
    def normalize(raw, receipt):
        value = normalize_envelope(raw, receipt)
        if value['status'] != 'completed':
            raise ProviderUnavailable('provider_'+value['status'])
        return value


class RecordedProvider:
    """Immutable response hashes anchor the private source to the accepted evidence."""
    def __init__(self, media_hash, duration_ms, profile='test'):
        self.profile = profile
        ev_root = Path(settings().provider_evidence_root).resolve()
        if profile == 'flash':
            if ev_root.name == 'stage1-bounded':
                self.root = ev_root.parent / 'stage2-bounded'
            elif (ev_root / 'stage2-bounded').is_dir():
                self.root = ev_root / 'stage2-bounded'
            else:
                self.root = ev_root
            index_path = ROOT / 'apps/api/recorded-50-index.json'
        else:
            if ev_root.name == 'stage2-bounded':
                self.root = ev_root.parent / 'stage1-bounded'
            elif (ev_root / 'stage1-bounded').is_dir():
                self.root = ev_root / 'stage1-bounded'
            else:
                self.root = ev_root
            index_path = ROOT / 'apps/api/recorded-index.json'

        if not index_path.exists():
            raise ProviderUnavailable('recorded_index_unavailable')
        index = json.loads(index_path.read_text())
        self.spec = next((v for v in index['media'] if v['sha256'] == media_hash), None)
        if self.spec is None:
            raise ProviderUnavailable('recorded_evidence_unavailable_for_this_upload')
        require(self.spec['duration_ms'] == duration_ms, 'recorded media duration mismatch')
        self.index = index
        self.media_hash = media_hash
        # Verify original is still identical; deletion never targets this source tree.
        metadata = json.loads(self.read('media.json'))[self.spec['name']]
        original = Path(metadata['path'])
        require(original.is_file() and digest(original.read_bytes()) == media_hash, 'original media hash mismatch')
        self.ledger = json.loads(self.read('ledger.json'))

    def read(self, name):
        require(name in self.index['artifact_sha256'] and Path(name).name == name, 'unknown recorded artifact')
        data = (self.root/name).read_bytes()
        require(digest(data) == self.index['artifact_sha256'][name], 'recorded artifact hash mismatch')
        return data

    @property
    def persona_ids(self):
        return self.spec['persona_ids']

    def response(self, label):
        call = next((c for c in self.ledger['calls'] if c['label'] == label), None)
        if call is None:
            raise ProviderUnavailable(f'recorded_call_unavailable: {label}')
        filename = f"response-{call['number']:03d}-{label}.json"
        data = self.read(filename)
        raw = json.loads(data)
        require(raw['id'] == call['response_id'] and raw['usage'] == call['usage'], 'receipt mismatch')
        normalized = MetaStandardAdapter.normalize(raw, call)
        return normalized, data, digest(data)

    def verdict(self, projection):
        scene = projection['scene']
        pid = projection['persona_id']
        require(pid in self.persona_ids, 'unknown recorded persona')
        expected = self.spec['scenes'][scene['scene_id']]
        require({k: scene[k] for k in ('scene_id', 'start_ms', 'end_ms')} == expected, 'recorded scene mismatch')
        if self.profile == 'flash':
            call_label = f"a-50-s{scene['scene_id']}-{pid}"
            evidence_id = f"a-50-{pid}-s{scene['scene_id']}"
        else:
            call_label = f"{self.spec['name']}-3-s{scene['scene_id']}-{pid}"
            evidence_id = f"{self.spec['name']}-3-{pid}-s{scene['scene_id']}"
        normalized, data, sha = self.response(call_label)
        reaction, evidence = normalize_verdict(
            normalized['output'],
            pid,
            scene['scene_id'],
            scene['start_ms'] / 1000,
            scene['end_ms'] / 1000,
            evidence_id,
        )
        return reaction, evidence, normalized, data, sha

    def notes(self):
        if self.profile == 'flash':
            return self.response('a-50-notes')
        return self.response(f"{self.spec['name']}-3-notes")

    def provenance(self):
        if self.profile == 'flash':
            limitations = [
                'Historical simulated responses replayed; no fresh model inference.',
                'Replay elapsed time is not provider latency. No new provider spend.',
                'Fifty simulated personas derived from five archetypes; not 50 distinct human behaviors.',
                'Local frames decoded from this upload. Transcript and OCR were not extracted in this run.',
                'Historical provider files and backup erasure are outside app-owned deletion.',
            ]
        else:
            limitations = [
                'Historical simulated responses replayed; no fresh model inference.',
                'Replay elapsed time is not provider latency. No new provider spend.',
                'Three simulated viewers are not a representative audience.',
                'Local frames decoded from this upload. Transcript and OCR were not extracted in this run.',
                'Historical provider files and backup erasure are outside app-owned deletion.',
            ]
        return dict(
            mode='recorded',
            label='Recorded inference · exact original media',
            source_sha=self.index['source_sha'],
            source_observed_at=self.index['observed_at'],
            media_sha256=self.media_hash,
            source_artifact_sha256=self.index['artifact_sha256'],
            model_ids=['muse-spark-1.3'],
            reported_versions=[None],
            training_cutoff='not provided',
            live_calls=0,
            limitations=limitations,
        )

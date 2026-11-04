"""Fictional candidate persona cards and catalog for Standard provider."""
import hashlib
import json
from pathlib import Path
from contracts.normalized import require, content_hash
from .config import ROOT

POLICIES_PATH = Path(__file__).parent / 'data/fifty-policies.json'
EXPECTED_POLICIES_HASH = '66d9649bf11e24fda80bddb721e0783f5c7ef72c0c203f448e70b5a744118ffd'


def _load_policies():
    require(POLICIES_PATH.is_file(), 'fifty-policies.json missing')
    raw_bytes = POLICIES_PATH.read_bytes()
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    require(file_hash == EXPECTED_POLICIES_HASH, f'fifty-policies.json hash mismatch: {file_hash}')
    data = json.loads(raw_bytes.decode('utf-8'))
    policies = data.get('policies', [])
    require(len(policies) == 50, f'expected 50 policies, got {len(policies)}')
    return policies, file_hash


_CACHED_POLICIES = None
_CACHED_HASH = None


def get_policies():
    global _CACHED_POLICIES, _CACHED_HASH
    if _CACHED_POLICIES is None:
        _CACHED_POLICIES, _CACHED_HASH = _load_policies()
    return _CACHED_POLICIES, _CACHED_HASH


def get_persona_ids(profile: str = 'test'):
    require(profile in ('test', 'flash'), f'invalid profile: {profile}')
    if profile == 'flash':
        return [f'p{i:03d}' for i in range(1, 51)]
    return ['p001', 'p002', 'p003']


def get_persona_card(persona_id: str):
    policies, _ = get_policies()
    require(isinstance(persona_id, str) and persona_id.startswith('p'), f'invalid persona id: {persona_id}')
    try:
        idx = int(persona_id[1:]) - 1
    except ValueError:
        raise ValueError(f'invalid persona id format: {persona_id}')
    require(0 <= idx < len(policies), f'persona id out of bounds: {persona_id}')
    policy = policies[idx]
    return dict(policy['card'])


def get_cast_hash(profile: str = 'test'):
    pids = get_persona_ids(profile)
    cards = {pid: get_persona_card(pid) for pid in pids}
    return content_hash(cards)

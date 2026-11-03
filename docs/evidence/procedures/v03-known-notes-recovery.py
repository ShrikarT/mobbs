"""One operator-assisted recovery of this coordinator's own known-400 test run.

No customer/original-owner run is permitted. Default dry-run. No provider HTTP
is sent here; --apply queues the real durable worker for one corrected notes
attempt. Original rejected receipt, all accepted decisions and backup survive.
"""
import copy, hashlib, json, os, subprocess, sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

P = Path(__file__).resolve().parent
ROOT = Path('C:/Users/Shrikar/orca/workspaces/viralist/codex-v03-preview')
SHA = '095fd2ba112d99fef72db8535e2a7f81d4f075f3'
RID = '1236b9c5fb0d47d7bfe19380591b5c27'
REQUEST = '450f235f-f095-4508-ba44-d509b1dfee42'
RUNTIME = Path('C:/Users/Shrikar/.codex/private-runs/viralist-v03-preview-20261103/runtime.json')
APPLY = sys.argv[1:] == ['--apply']
assert sys.argv[1:] in ([], ['--apply'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip() == SHA
assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
assert not (RUNTIME.parent/'operational_pause.marker').exists(), 'Never clear an uncertainty pause'
summary = json.loads((P/'failed-journey-summary.json').read_text())
assert summary['run_id'] == RID and summary['source_sha'] == 'df43e7d1077928756263c34ca1dd0036898d3070'
cfg = json.loads(RUNTIME.read_text(encoding='utf-8-sig'))
assert cfg['s3_bucket'] == 'viralist-v03-preview-20261103'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.path.insert(0,str(ROOT))
from apps.api.app.standard_provider import NOTES_SCHEMA
assert set(NOTES_SCHEMA['required']) == set(NOTES_SCHEMA['properties']) == {'notes','limitations'}

def encoded(value):
    return json.dumps(value, sort_keys=True, default=str, separators=(',',':'))

with psycopg.connect(cfg['database_url'],row_factory=dict_row) as c:
    target = c.execute('SELECT video_id FROM runs WHERE id=%s',(RID,)).fetchone()
    assert target
    # Same lock order as the production fence: video, job, then run.
    video = c.execute('SELECT * FROM videos WHERE id=%s FOR UPDATE',(target['video_id'],)).fetchone()
    jobs = c.execute('SELECT * FROM jobs WHERE run_id=%s FOR UPDATE',(RID,)).fetchall()
    run = c.execute('SELECT * FROM runs WHERE id=%s FOR UPDATE',(RID,)).fetchone()
    assert video and not video['deleted_at']
    assert len(jobs)==1 and jobs[0]['kind']=='analysis' and jobs[0]['status']=='complete'
    assert run['status']=='failed' and run['error_code']=='provider_http_error_400' and run['report'] is None
    cps = c.execute('SELECT * FROM checkpoints WHERE run_id=%s ORDER BY persona_id',(RID,)).fetchall()
    calls = c.execute('SELECT * FROM provider_calls WHERE run_id=%s ORDER BY unit FOR UPDATE',(RID,)).fetchall()
    reactions = c.execute('SELECT * FROM reactions WHERE run_id=%s ORDER BY persona_id,scene_id',(RID,)).fetchall()
    assert len(cps)==50 and all(x['status'] in ('stopped','complete') for x in cps)
    rejected = [x for x in calls if x['unit']=='notes']
    assert len(rejected)==1 and len([x for x in calls if x['unit'].startswith('notes')])==1
    old = rejected[0]; receipt=old['receipt']
    assert old['status']=='failed' and receipt['http_status']==400 and receipt['request_id']==REQUEST
    assert receipt['error']['code']=='provider_http_error_400' and receipt['error']['charge_state']=='unconfirmed'
    accepted = [x for x in calls if x['unit']!='notes']
    assert len(accepted)==346 and all(x['status']=='accepted' for x in accepted) and len(reactions)==346
    assert old['audit'].get('supported_triggers'), 'Only the known supported notes failure is recoverable'
    limit=min(651,run['manifest']['requested']*len(video['features']['scenes'])+1)
    assert len(calls)+1 <= limit, 'Do not raise the existing call ceiling'
    marker=P/'corrected-notes-attempt.attempted'
    assert not marker.exists(), 'One corrected attempt already recorded; inspect it, never repeat blindly'
    proposal=dict(run_id=RID,source_sha=SHA,old_http_request=REQUEST,accepted_decisions_reused=346,
                  cast=dict(Counter(x['status'] for x in cps)),existing_calls=len(calls),new_calls_maximum=1,
                  resulting_calls_maximum=len(calls)+1,unchanged_run_ceiling=limit,
                  accepted_digest=hashlib.sha256(encoded(accepted).encode()).hexdigest(),
                  reactions_digest=hashlib.sha256(encoded(reactions).encode()).hexdigest(),
                  reason='Known HTTP400 request validation; required limitations schema corrected; explicit local verification recovery')
    if APPLY:
        backup=dict(video=video,run=run,jobs=jobs,checkpoints=cps,provider_calls=calls,reactions=reactions)
        with (P/'notes-recovery-before.private.json').open('x',encoding='utf-8') as f:f.write(encoded(backup))
        with marker.open('x',encoding='utf-8') as f:f.write(encoded(proposal))
        audit=copy.deepcopy(old['audit'])
        audit['_operator_recovery']=dict(original_unit='notes',original_run_status='failed',
            original_error='provider_http_error_400',from_source=summary['source_sha'],to_source=SHA,
            reason=proposal['reason'],at=datetime.now(timezone.utc).isoformat())
        c.execute("UPDATE provider_calls SET unit='notes:rejected:1',audit=%s WHERE run_id=%s AND unit='notes'",(Jsonb(audit),RID))
        c.execute("UPDATE runs SET status='processing',stage='reporting',error_code=NULL,completed_at=NULL WHERE id=%s",(RID,))
        c.execute("UPDATE jobs SET status='queued',generation=generation+1,lease_until=NULL,available_at=now() WHERE id=%s",(jobs[0]['id'],))
    (P/'notes-recovery-proposal.json').write_text(json.dumps(proposal,indent=2))
print(json.dumps(dict(mode='QUEUED_ONE_CORRECTED_NOTES' if APPLY else 'DRY_RUN',**proposal)))

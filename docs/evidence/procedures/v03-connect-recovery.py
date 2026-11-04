"""Operator recovery for a verified legacy pre-request ConnectTimeout only.

Dry run by default. Never reconciles read/write/HTTP failures or unknown dispatches.
Preserves the immutable manifest, accepted data and original sanitized receipt.
The matching worker must be stopped before --apply, then restarted at the fix SHA.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from apps.api.app.config import get_effective_runtime_path
from apps.api.app.db import connection,Jsonb
from apps.api.app.worker import clear_operational_pause


def fingerprint(rows):
    return hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    assert re.fullmatch('[a-f0-9]{32}',args.run_id),'Invalid run identity'
    private=Path(get_effective_runtime_path()).resolve().parent/'connect-recovery'
    assert not private.is_relative_to(ROOT),'Recovery evidence must stay outside Git'
    with connection() as conn:
        run=conn.execute('SELECT r.*,v.deleted_at FROM runs r JOIN videos v ON v.id=r.video_id WHERE r.id=%s FOR UPDATE OF r,v',(args.run_id,)).fetchone()
        assert run and run['deleted_at'] is None and run['status']=='failed' and run['error_code']=='uncertain_provider_charge'
        assert run['manifest']['provider_mode']=='standard' and run['report'] is None
        assert not conn.execute("SELECT 1 FROM jobs WHERE status='leased' AND kind='analysis'").fetchone(),'Stop the matching worker first'
        assert not conn.execute("SELECT 1 FROM provider_calls WHERE status='dispatched'").fetchone(),'Unresolved request: recovery refused'
        failures=conn.execute("SELECT * FROM provider_calls WHERE status='failed'").fetchall()
        assert len(failures)==1 and failures[0]['run_id']==args.run_id,'Other uncertain failures: recovery refused'
        call=failures[0];original=call['receipt'];error=original.get('error') or {}
        assert error.get('code')=='provider_transport_error' and error.get('error_class')=='ConnectTimeout'
        audit=call['audit'];pid=audit['persona_id'];scene=audit['scene']['scene_id']
        assert call['unit']==f'{pid}:{scene}'
        cp=conn.execute('SELECT * FROM checkpoints WHERE run_id=%s AND persona_id=%s FOR UPDATE',(args.run_id,pid)).fetchone()
        assert cp['status']=='failed' and cp['next_scene']==scene
        assert not conn.execute('SELECT 1 FROM reactions WHERE run_id=%s AND persona_id=%s AND scene_id=%s',(args.run_id,pid,scene)).fetchone()
        saved=conn.execute('SELECT persona_id,scene_id,reaction,evidence FROM reactions WHERE run_id=%s ORDER BY persona_id,scene_id',(args.run_id,)).fetchall()
        # The archived connection record consumes one ledger row; retain the call ceiling.
        assert conn.execute("SELECT 1 FROM checkpoints WHERE run_id=%s AND status='stopped'",(args.run_id,)).fetchone(),'Ceiling margin not established'
        before=fingerprint(saved)
        print(f'Eligible pre-request connect failure; {len(saved)} saved decisions remain unchanged.')
        if not args.apply:return
        private.mkdir(parents=True,exist_ok=True)
        backup=private/f'{args.run_id}.json'
        assert not backup.exists(),'Recovery already attempted; refusing another apply'
        # No media, impressions, reasons, report copy or raw provider body in this backup.
        backup.write_text(json.dumps(dict(run_id=args.run_id,unit=call['unit'],original_receipt=original,
            original_audit_sha256=fingerprint(audit),accepted_count=len(saved),accepted_sha256=before,
            manifest_sha256=fingerprint(run['manifest'])),indent=2),encoding='utf-8')
        receipt=dict(mode='transport_audit',new_provider_calls=0,cost_usd=None,usage=None,
            reconciliation='Legacy ConnectTimeout before HTTP request body; bounded continuation authorized by owner bug-fix request.',
            original_receipt=original)
        conn.execute("UPDATE provider_calls SET unit=unit||':connect-failed:1',status='reconciled_not_sent',receipt=%s WHERE run_id=%s AND unit=%s",(Jsonb(receipt),args.run_id,call['unit']))
        conn.execute("UPDATE checkpoints SET status='active' WHERE run_id=%s AND persona_id=%s",(args.run_id,pid))
        conn.execute("UPDATE runs SET status='queued',stage='simulating',error_code=NULL WHERE id=%s",(args.run_id,))
        jobs=conn.execute("UPDATE jobs SET status='queued',generation=generation+1,lease_until=NULL,available_at=now() WHERE run_id=%s AND kind='analysis' RETURNING id",(args.run_id,)).fetchall()
        assert len(jobs)==1
        after=conn.execute('SELECT persona_id,scene_id,reaction,evidence FROM reactions WHERE run_id=%s ORDER BY persona_id,scene_id',(args.run_id,)).fetchall()
        assert fingerprint(after)==before
    # Only this proven not-sent failure was reconciled; no other uncertain call exists.
    clear_operational_pause()
    print('Queued remaining work; original receipt archived; accepted data and manifest preserved.')


if __name__=='__main__':main()

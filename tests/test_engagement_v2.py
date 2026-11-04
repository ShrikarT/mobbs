import unittest
from contracts.normalized import normalize_verdict

class EngagementV2Tests(unittest.TestCase):
    def item(self):
        return {'persona_id':'p001','still_watching':True,'reason':'The demo makes the next step clear.',
                'impression':'Useful demo','actions':['like','comment','follow'],'confused':False,
                'cta_understood':True,'quick_reaction':'okay, that’s handy!','comment_text':'Would try this.'}

    def test_new_signals_preserve_follow_comment_and_short_reaction(self):
        rx,ev=normalize_verdict({'verdicts':[self.item()]},'p001',0,0,3,'e1',extended_signals=True)
        self.assertIn('follow',[a['type'] for a in rx['actions']])
        self.assertEqual(rx['signals']['confused'],False)
        self.assertEqual(rx['signals']['cta_understood'],True)
        self.assertEqual(ev['comment_text'],'Would try this.')
        self.assertLessEqual(len(ev['quick_reaction']),60)

    def test_missing_call_to_action_stays_unknown(self):
        item=self.item();item['cta_understood']=None
        rx,_=normalize_verdict({'verdicts':[item]},'p001',0,0,3,'e1',extended_signals=True)
        self.assertIsNone(rx['signals']['cta_understood'])

    def test_long_reaction_and_comment_without_action_rejected(self):
        item=self.item();item['quick_reaction']='word '*20
        with self.assertRaises(ValueError):normalize_verdict({'verdicts':[item]},'p001',0,0,3,'e1',extended_signals=True)
        item=self.item();item['actions']=['like']
        with self.assertRaises(ValueError):normalize_verdict({'verdicts':[item]},'p001',0,0,3,'e1',extended_signals=True)

    def test_legacy_path_does_not_claim_new_signals(self):
        item={key:self.item()[key] for key in ['persona_id','still_watching','reason','impression','actions']};item['actions']=['like']
        rx,ev=normalize_verdict({'verdicts':[item]},'p001',0,0,3,'e1')
        self.assertIsNone(rx['signals']['confused']);self.assertNotIn('quick_reaction',ev)

    def test_report_counts_unique_people_and_eligible_ratings(self):
        from apps.api.app.reporting import build_report
        manifest={'profile':'test','provider_mode':'recorded','requested':3,'persona_ids':['p001','p002','p003'],'signals_version':'engagement-v2'}
        video={'metadata':{'duration_ms':6000},'features':{'scenes':[{'scene_id':0,'start_ms':0,'end_ms':3000},{'scene_id':1,'start_ms':3000,'end_ms':6000}]}}
        rows=[]
        for pid in manifest['persona_ids']:
            for sid in range(2):
                item=self.item();item['persona_id']=pid
                item['actions']=['like','comment','follow'] if pid=='p001' else []
                item['comment_text']='Would try this.' if pid=='p001' else None
                item['confused']=pid=='p002'
                item['cta_understood']=None if pid=='p003' else pid=='p001'
                rx,ev=normalize_verdict({'verdicts':[item]},pid,sid,sid*3,(sid+1)*3,pid+str(sid),extended_signals=True)
                rows.append({'reaction':rx,'evidence':ev})
        report=build_report(manifest,video,[{'persona_id':pid,'status':'complete'} for pid in manifest['persona_ids']],rows,None,'test',{'output':{'notes':[]}},[])
        self.assertAlmostEqual(report['engagement']['follow']['observed'],100/3)
        self.assertEqual(report['engagement']['follow']['denominator'],3)
        self.assertAlmostEqual(report['scores']['clarity']['observed'],200/3)
        self.assertEqual(report['scores']['cta']['denominator'],2)
        self.assertEqual(report['scores']['cta']['observed'],50)
        self.assertTrue(report['coverage']['confused'])

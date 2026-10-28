import copy
import json
import unittest
from pathlib import Path
from contracts.normalized import (
    cast_status, milliseconds, normalize_envelope, normalize_note,
    normalize_verdict, parse_json, stop_trigger, validate_deletion,
    validate_event, validate_fixture, validate_reaction, may_publish_job,
)


def fixture():
    return parse_json(Path('docs/contracts/vertical-slice.v1.json').read_text())


class NormalizationTests(unittest.TestCase):
    def setUp(self):
        self.raw = {'verdicts': [dict(persona_id='p1', still_watching=True,
                    actions=['save'], reason='I want to see the demonstration.', impression='Waiting.') ]}

    def convert(self, value=None, **kw):
        args = dict(persona_id='p1', scene_id=0, start_sec=0, end_sec=3, evidence_id='e1')
        args.update(kw)
        return normalize_verdict(value or self.raw, **args)

    def test_continued_reason_and_unknowns_preserved(self):
        r, e = self.convert()
        self.assertIsNone(r['drop_reason'])
        self.assertEqual(e['quote'], self.raw['verdicts'][0]['reason'])
        self.assertIsNone(r['actions'][0]['at_ms'])
        self.assertEqual(r['actions'][0]['timing'], 'unobserved')
        self.assertIsNone(r['signals']['confused'])

    def test_stopped_reason(self):
        self.raw['verdicts'][0]['still_watching'] = False
        r, e = self.convert()
        self.assertEqual(r['drop_reason'], e['quote'])

    def test_bad_legacy_verdicts(self):
        mutations = [lambda v: v['verdicts'].append(v['verdicts'][0]),
            lambda v: v['verdicts'][0].update(persona_id='other'),
            lambda v: v['verdicts'][0].update(actions=['execute_tool']),
            lambda v: v['verdicts'][0].update(actions=['follow']),
            lambda v: v['verdicts'][0].update(actions=['save', 'save']),
            lambda v: v['verdicts'][0].update(still_watching=1),
            lambda v: v['verdicts'][0].update(reason=''),
            lambda v: v['verdicts'][0].update(impression='word '*31)]
        for mutation in mutations:
            with self.subTest(mutation=mutations.index(mutation)):
                value = copy.deepcopy(self.raw); mutation(value)
                with self.assertRaises(ValueError): self.convert(value)

    def test_ms_half_up_and_invalid_times(self):
        self.assertEqual(milliseconds(1.2345), 1235)
        for value in (float('nan'), float('inf'), -1, True, '1'):
            with self.assertRaises(ValueError): milliseconds(value)
        with self.assertRaises(ValueError): self.convert(start_sec=3, end_sec=3)

    def test_canonical_actions_and_bounds(self):
        r, _ = self.convert()
        r['actions'] = [dict(type='follow', at_ms=2999, timing='observed')]
        validate_reaction(r, {'p1'}, {0: (0, 3000)})
        for at in (3000, -1, float('nan'), 1.5, True):
            r['actions'][0]['at_ms'] = at
            with self.assertRaises(ValueError): validate_reaction(r, {'p1'}, {0: (0, 3000)})
        r['actions'] = []; r['impression_update'] = 'word '*61
        with self.assertRaises(ValueError): validate_reaction(r, {'p1'}, {0: (0, 3000)})

    def test_strict_json(self):
        for value in ('{"a":NaN}', '{"a":Infinity}', '{"a":1e999}', '{"a":1,"a":2}'):
            with self.assertRaises(ValueError): parse_json(value)

    def test_saved_envelopes(self):
        data = parse_json(Path('docs/contracts/provider-saved.v1.json').read_text())
        self.assertEqual(data['refusal'], 'unobserved')
        for case in data['examples']:
            with self.subTest(kind=case['kind']):
                actual = normalize_envelope(case['raw_projection'], case['receipt'])
                self.assertEqual(actual, case['normalized'])
                self.assertIsNone(actual['reported_version'])
                self.assertEqual(actual['cancellation'], 'unknown')
        incomplete = data['examples'][1]['normalized']
        self.assertEqual(incomplete['status'], 'incomplete')
        self.assertEqual(incomplete['usage']['output_tokens'], 600)
        self.assertIsNone(incomplete['output'])
        self.assertEqual(data['examples'][2]['normalized']['error']['charge_state'], 'uncertain')

    def test_envelope_errors_and_unobserved_refusal(self):
        receipt = dict(http_status=200, latency_sec=.001, requested_model='test', request_id='synthetic')
        raw = dict(status='completed', output=[dict(type='message', content=[dict(type='refusal', refusal='SYNTHETIC')])])
        self.assertEqual(normalize_envelope(raw, receipt)['status'], 'refused')
        for change in [dict(status='future'), dict(output=[]), dict(output=[dict(type='tool_call')])]:
            value = dict(raw);value.update(change)
            with self.assertRaises(ValueError): normalize_envelope(value, receipt)

    def test_supported_note_and_negative_mutations(self):
        f = fixture(); e = f['expected']; n = e['note']
        raw = dict(start_sec=0, end_sec=3, evidence_ids=n['evidence_refs'],
                   quotes=[q['text'] for q in n['quotes']], finding=n['interpretation'], suggested_edit=n['fix'])
        evidence = {x['id']: x for x in e['evidence']}; trigger=e['observations'][0]
        self.assertEqual(normalize_note(raw, evidence, trigger, n['id']), n)
        for change in [dict(evidence_ids=['missing']), dict(quotes=['invented quote']),
                       dict(start_sec=float('inf')), dict(end_sec=4), dict(suggested_edit='Show synthetic product UI.')]:
            value=dict(raw);value.update(change)
            with self.assertRaises(ValueError): normalize_note(value, evidence, trigger, n['id'])
        with self.assertRaises(ValueError): normalize_note(raw, evidence, None, n['id'])

    def test_detector_no_trigger_and_duplicates(self):
        r, _ = self.convert()
        self.assertIsNone(stop_trigger('t', 0, 0, 3000, [r]))
        self.assertIsNone(stop_trigger('t', 1, 3000, 6000, [r]))
        with self.assertRaises(ValueError): stop_trigger('t', 0, 0, 3000, [r, r])

    def test_cast_profiles(self):
        self.assertEqual(cast_status('test', 2, 2, 0, 0), 'complete_test_profile')
        self.assertEqual(cast_status('test', 2, 0, 2, 0), 'failed')
        self.assertEqual(cast_status('flash', 50, 39, 11, 0), 'incomplete')
        self.assertEqual(cast_status('flash', 50, 49, 1, 0), 'incomplete')
        for args in [('flash',2,2,0,0), ('test',2,2,1,0), ('unknown',2,2,0,0)]:
            with self.assertRaises(ValueError): cast_status(*args)

    def test_fixture_validates(self):
        validate_fixture(fixture())

    def test_fixture_negative_mutations(self):
        mutations = [lambda f: f['expected']['trust'].update(mode='live'),
            lambda f: f['expected']['trust'].update(feature_sha256='0'*64),
            lambda f: f['expected']['cast'].update(status='incomplete'),
            lambda f: f['expected']['cast'].update(stopped=0),
            lambda f: f['batches'][1]['persona_ids'].append('p1'),
            lambda f: f['verdicts'][1].update(persona_id='missing'),
            lambda f: f['expected']['note'].update(evidence_refs=['missing']),
            lambda f: f['expected']['evidence'][0].update(quote='invented'),
            lambda f: f['expected']['metric'].update(denominator=50),
            lambda f: f['expected'].update(completion_count=2),
            lambda f: f['expected'].update(completion_samples_percent=[100,100,100]),
            lambda f: f['expected']['deletion'].update(can_claim_complete=True),
            lambda f: f['event_example'].update(type='unknown')]
        for i, mutation in enumerate(mutations):
            with self.subTest(mutation=i):
                f=fixture();mutation(f)
                with self.assertRaises(ValueError): validate_fixture(f)

    def test_deletion_pending_retry_complete_repeat_and_fencing(self):
        f=fixture()
        for d in [f['expected']['deletion']] + f['deletion_examples']: validate_deletion(d)
        for mutation in [lambda d: d.update(repeat_deletion_id='new'),
                         lambda d: d.update(access_revoked_at=None),
                         lambda d: d['targets'].pop('jobs'),
                         lambda d: d.update(completed_at='2026-10-28T00:00:00Z')]:
            d=copy.deepcopy(f['deletion_examples'][-1]);mutation(d)
            with self.assertRaises(ValueError):validate_deletion(d)
        self.assertFalse(may_publish_job(1,2,False))
        self.assertFalse(may_publish_job(2,2,True))
        self.assertTrue(may_publish_job(2,2,False))


if __name__ == '__main__': unittest.main()

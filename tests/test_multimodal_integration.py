"""Production API/worker/storage; only model HTTP responses are controlled."""
import json
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from apps.api.app.config import settings
from apps.api.app.db import connection, uid
from apps.api.app.main import app
from apps.api.app.standard_provider import StandardProvider
from apps.api.app.worker import process_once, claim, clear_operational_pause
from apps.api.app.multimodal import durable_feature
from tests.test_multimodal import envelope


@unittest.skipUnless(os.environ.get('MOBBS_MULTIMODAL_FIXTURE'), 'requires isolated multimodal runtime/fixture')
class MultimodalJourneyTests(unittest.TestCase):
    def setUp(self):
        self.assertEqual(settings().s3_bucket,'mobbs-multimodal-20261104')
        clear_operational_pause()
        self.client = TestClient(app, base_url=settings().origin)
        self.headers = {'Origin': settings().origin}
        result = self.client.post('/sessions', headers=self.headers)
        self.headers.update({'X-CSRF-Token': result.json()['csrf']})
        self.video = None

    def post(self, url, **kwargs):
        headers = {**self.headers, 'Idempotency-Key': uid()}
        if 'content' in kwargs: headers['Content-Type'] = 'video/mp4'
        return self.client.post(url, headers=headers, **kwargs)

    def start(self):
        response = self.post('/videos', content=Path(os.environ['MOBBS_MULTIMODAL_FIXTURE']).read_bytes())
        self.assertEqual(response.status_code, 201, response.text)
        self.video = response.json()['video_id']
        with patch('apps.api.app.main.settings', return_value=replace(settings(), provider_mode='standard')):
            response = self.post('/runs', json={'video_id': self.video, 'profile': 'test'})
        self.assertEqual(response.status_code, 202, response.text)
        return response.json()['run_id']

    def tearDown(self):
        if self.video:
            response = self.client.delete('/videos/'+self.video, headers={**self.headers, 'Idempotency-Key': uid()})
            self.assertIn(response.status_code, (200,202))
            for _ in range(5):
                if not process_once(): break

    def test_audio_visual_context_report_and_no_post_skip_dispatch(self):
        run = self.start()
        counts = {'visual': 0, 'audio': 0}
        seen = []
        def handler(request):
            if request.url.path.endswith('/asr/transcribe'):
                i = counts['audio'];counts['audio'] += 1
                text = 'opening words' if i == 0 else 'future words'
                return httpx.Response(200, json={'transcript': text, 'turns': [{'startMs': 0, 'endMs': 1000, 'transcript': text}], 'audioDurationMs': 3000})
            body = json.loads(request.content)
            if body['text']['format']['name'] == 'scene_observation':
                counts['visual'] += 1
                return httpx.Response(200, json=envelope({'description': 'isolated clip', 'visible_text': 'demo', 'motion': 'scroll'}))
            prompt = body['input'][0]['content'][0]['text']
            if 'verdicts' in body['text']['format']['schema']['properties']:
                context = json.loads(prompt[prompt.index('{"viewer"'):])
                pid = context['viewer']['persona_id'];scene = context['current_segment'];index = scene['scene_id']
                seen.append((pid,index))
                self.assertEqual(scene['features']['transcript']['text'], 'opening words' if index == 0 else 'future words')
                return httpx.Response(200, json=envelope({'verdicts': [{'persona_id': pid, 'still_watching': pid != 'p001', 'reason': 'Test simulated reason', 'impression': 'Test impression', 'actions': []}]}))
            return httpx.Response(200, json=envelope({'notes': [], 'limitations': []}))
        def factory(media_hash, duration, profile='test', lease=None):
            return StandardProvider(media_hash,duration,profile=profile,lease=lease,transport=httpx.MockTransport(handler))
        for _ in range(15):
            if not process_once(provider_factory=factory): break
        response = self.client.get('/runs/'+run+'/report')
        if response.status_code != 200:
            with connection() as conn:
                state = conn.execute('SELECT status,stage,error_code FROM runs WHERE id=%s',(run,)).fetchone()
                calls = conn.execute('SELECT unit,status,receipt FROM provider_calls WHERE run_id=%s',(run,)).fetchall()
            self.fail(str({'state':state,'calls':calls,'seen':seen,'counts':counts}))
        self.assertEqual(response.status_code,200,response.text)
        report = response.json()
        self.assertTrue(report['coverage']['transcript'])
        self.assertIn('muse-voice-transcribe-1.0', report['trust']['model_ids'])
        self.assertEqual(counts, {'visual': 2, 'audio': 2})
        self.assertNotIn(('p001',1), seen)
        self.assertEqual(report['cast']['effective'],3)
        with connection() as conn:
            self.assertFalse(conn.execute("SELECT 1 FROM provider_calls WHERE run_id=%s AND status!='accepted'",(run,)).fetchone())
        self.assertEqual(self.client.get('/runs/'+run+'/report').json(),report)

    def test_accepted_feature_reused_and_ambiguous_unit_never_resent(self):
        self.start();lease = claim()
        send_count = []
        def send():
            send_count.append(1)
            return {'text': 'current'}, b'{}', {'mode': 'standard'}
        self.assertEqual(durable_feature(lease,'prep:audio:0',send),{'text':'current'})
        self.assertEqual(durable_feature(lease,'prep:audio:0',send),{'text':'current'})
        self.assertEqual(len(send_count),1)
        def timeout(): raise httpx.ReadTimeout('unknown')
        with self.assertRaisesRegex(ValueError,'uncertain_provider_charge'):
            durable_feature(lease,'prep:audio:1',timeout)
        with self.assertRaisesRegex(ValueError,'uncertain_provider_charge'):
            durable_feature(lease,'prep:audio:1',send)
        self.assertEqual(len(send_count),1)

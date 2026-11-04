import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from apps.api.app.standard_provider import StandardProvider
from apps.api.app.scene_models import SceneModels, VOICE_MODEL
from apps.api.app.worker import project, validate_projection


def envelope(output):
    return {'id': 'test-response', 'model': 'muse-spark-1.3', 'status': 'completed',
            'usage': {'input_tokens': 20, 'output_tokens': 20, 'total_tokens': 40},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]}


class SceneModelTests(unittest.TestCase):
    def test_audio_request_and_absolute_scene_timing(self):
        requests = []
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'transcript': 'current words', 'audioDurationMs': 3000,
                                            'turns': [{'startMs': 100, 'endMs': 2000, 'transcript': 'current words'}]})
        provider = StandardProvider('test', 8000, transport=httpx.MockTransport(handler))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'scene.wav';path.write_bytes(b'isolated current audio')
                result, _, receipt = SceneModels(provider).transcribe(path, {'start_ms': 3000, 'end_ms': 6000})
            self.assertEqual(result['turns'][0]['start_ms'], 3100)
            self.assertEqual(result['turns'][0]['end_ms'], 5000)
            self.assertEqual(receipt['model_id'], VOICE_MODEL)
            self.assertIn('multipart/form-data', requests[0].headers['content-type'])
            self.assertIn(VOICE_MODEL.encode(), requests[0].content)
        finally: provider.close()

    def test_native_clip_is_inline_without_stored_provider_file(self):
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, json=envelope({'description': 'red screen', 'visible_text': 'hello', 'motion': 'scroll'}))
        provider = StandardProvider('test', 3000, transport=httpx.MockTransport(handler))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'scene.mp4';path.write_bytes(b'current-only-clip')
                result, _, receipt = SceneModels(provider).observe(path, {'start_ms': 0, 'end_ms': 3000})
            self.assertEqual(result['motion'], 'scroll')
            part = captured[0]['input'][0]['content'][1]
            self.assertEqual(part['type'], 'input_file')
            self.assertTrue(part['file_data'].startswith('data:video/mp4;base64,'))
            self.assertFalse(captured[0]['store'])
            self.assertGreater(receipt['cost_usd'], 0)
        finally: provider.close()

    def test_future_feature_injection_and_post_skip_rejected(self):
        scene = {'scene_id': 0, 'start_ms': 0, 'end_ms': 3000, 'frame_ref': 'scene0',
                 'media_pipeline': 'scene-av-v1', 'transcript': {'text': 'opening'},
                 'observations': {'description': 'opening only'}, 'ocr': 'opening'}
        checkpoint = {'persona_id': 'p001', 'status': 'active', 'next_scene': 0, 'impression': ''}
        value = project(scene, checkpoint)
        validate_projection(value, scene, checkpoint)
        self.assertEqual(value['scene_features']['transcript']['text'], 'opening')
        import copy
        injected = copy.deepcopy(value);injected['scene_features']['transcript']['text'] = 'future secret'
        with self.assertRaises(ValueError): validate_projection(injected, scene, checkpoint)
        with self.assertRaises(ValueError): validate_projection(value, scene, {**checkpoint, 'status': 'stopped'})

    def test_transport_timeout_is_not_retried(self):
        calls = []
        def handler(request):
            calls.append(request);raise httpx.ReadTimeout('unknown provider outcome')
        provider = StandardProvider('test', 3000, transport=httpx.MockTransport(handler))
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)/'scene.wav';path.write_bytes(b'test')
                with self.assertRaisesRegex(ValueError, 'uncertain_provider_charge'):
                    SceneModels(provider).transcribe(path, {'start_ms': 0, 'end_ms': 3000})
            self.assertEqual(len(calls), 1)
        finally: provider.close()

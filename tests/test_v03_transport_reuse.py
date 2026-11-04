"""Regression checks against the production adapter; no live model calls."""
import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from apps.api.app.standard_provider import StandardProvider, ProviderUnavailable
from apps.api.app.worker import sanitize_error_receipt
from apps.api.app.domain import LeaseLost
from tests.test_v03_standard_app import make_verdict_response


def projection(pid='p001', frame='frame-0', scene=0):
    return dict(persona_id=pid,scene=dict(scene_id=scene,start_ms=scene*3000,end_ms=(scene+1)*3000),allowed_media_refs=[frame],own_impression='')


def response(request):
    text=json.loads(request.content)['input'][0]['content'][0]['text']
    pid=json.loads(text[text.index('{'):])['viewer']['persona_id']
    return httpx.Response(200,json=make_verdict_response(pid))


class TestTransportReuse(unittest.TestCase):
    def setUp(self):
        self.config=patch('apps.api.app.standard_provider.settings',return_value=SimpleNamespace(model_api_key='test-only'))
        self.config.start()
        self.storage=patch('apps.api.app.standard_provider.Storage').start()
        self.storage.return_value.get.side_effect=lambda key:{'Body':io.BytesIO(b'jpeg-fixture')}

    def tearDown(self):
        patch.stopall()

    def test_parallel_units_reuse_one_owned_client(self):
        provider=StandardProvider('synthetic',4000,profile='flash',transport=httpx.MockTransport(response))
        with ThreadPoolExecutor(max_workers=8) as pool:
            clients=list(pool.map(lambda _:provider._get_client(),range(8)))
        try:self.assertEqual(len({id(c) for c in clients}),1)
        finally:
            for client in clients:client.close()

    def test_parallel_personas_fetch_each_allowed_frame_once(self):
        provider=StandardProvider('synthetic',4000,profile='flash',transport=httpx.MockTransport(response))
        try:
            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(lambda i:provider.verdict(projection(f'p{i:03}')),range(1,9)))
            self.assertEqual(self.storage.return_value.get.call_count,1)
            self.storage.return_value.get.assert_called_with('frame-0')
        finally:
            close=getattr(provider,'close',None)
            if close:close()

    def test_connect_timeout_is_retried_once_without_resending_a_sent_request(self):
        calls=[]
        def transport(request):
            calls.append(request)
            if len(calls)==1:raise httpx.ConnectTimeout('synthetic connect failure',request=request)
            return response(request)
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            provider=StandardProvider('synthetic',4000,profile='flash',client=client)
            result=provider.verdict(projection())
        self.assertEqual(len(calls),2)
        self.assertEqual(result[0]['persona_id'],'p001')
        self.assertEqual(provider.live_calls,1)

    def test_read_timeout_is_not_retried_and_remains_uncertain(self):
        calls=[]
        def transport(request):
            calls.append(request)
            raise httpx.ReadTimeout('synthetic after-send timeout',request=request)
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            provider=StandardProvider('synthetic',4000,profile='flash',client=client)
            with self.assertRaises(ProviderUnavailable) as raised:provider.verdict(projection())
        self.assertEqual(len(calls),1)
        self.assertEqual(sanitize_error_receipt(raised.exception)['error']['charge_state'],'uncertain')

    def test_exhausted_connect_failure_is_bounded_and_not_a_server_500(self):
        calls=[]
        def transport(request):
            calls.append(request)
            raise httpx.ConnectTimeout('synthetic connect failure',request=request)
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            provider=StandardProvider('synthetic',4000,profile='flash',client=client)
            with self.assertRaises(ProviderUnavailable) as raised:provider.verdict(projection())
        self.assertEqual(len(calls),2)
        receipt=sanitize_error_receipt(raised.exception)
        self.assertEqual(receipt['error']['code'],'provider_connection_unavailable')
        self.assertEqual(receipt['error']['charge_state'],'unconfirmed')
        self.assertIsNone(receipt['http_status'])

    def test_deleted_or_cancelled_lease_prevents_connection_retry(self):
        calls=[]
        def transport(request):
            calls.append(request)
            raise httpx.ConnectTimeout('synthetic pre-request failure',request=request)
        with httpx.Client(transport=httpx.MockTransport(transport)) as client:
            provider=StandardProvider('synthetic',4000,profile='flash',client=client,lease={'id':'synthetic','run_id':'synthetic'})
            with patch('apps.api.app.standard_provider.connection'),patch('apps.api.app.standard_provider.fence',side_effect=LeaseLost('deleted')):
                with self.assertRaises(LeaseLost):provider.verdict(projection())
        self.assertEqual(len(calls),1)

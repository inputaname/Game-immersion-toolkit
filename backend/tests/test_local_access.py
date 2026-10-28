"""Exercise the actual ASGI boundary without starting capture or local services."""
import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend import api
from backend.models import AppSettings, CaptureSnapshot


ORIGINS = [f'http://{host}:{port}' for host in ('localhost', '127.0.0.1') for port in (3000, 3001)]
BAD_ORIGINS = ['https://example.test', 'null', '', 'localhost', 'http://localhost:3000/',
               'http://localhost.evil.test:3000', 'http://localhost:3000@evil.test',
               'http://127.0.0.1:9999', 'https://localhost:3000']
BAD_HOSTS = ['', 'example.test', 'localhost.evil.test:8766', 'localhost@evil.test',
             'localhost:abc', 'localhost:65536', 'localhost:0', 'localhost:8766/path', '[::1]:8766']


@pytest.fixture
def local_client(monkeypatch):
    calls = []

    def record(kind, value=None):
        calls.append(kind)
        return value

    async def broadcast(event):
        calls.append('broadcast')

    async def stop():
        return record('stop', True)

    runtime = SimpleNamespace(
        capture=SimpleNamespace(start=lambda: record('start', True), stop=stop,
                                snapshot=lambda: record('snapshot', CaptureSnapshot())),
        settings=SimpleNamespace(save=lambda value: record('save', value)),
        hub=api.EventHub(), status=lambda: record('status', {'synthetic': True}),
        transcript=SimpleNamespace(list=lambda **_: record('lines', []), list_favorites=lambda **_: []),
        speakers=SimpleNamespace(enrich=lambda line: line))
    monkeypatch.setattr(api, 'runtime', runtime, raising=False)
    return TestClient(api.app, base_url='http://127.0.0.1:8766'), calls


@pytest.mark.parametrize('origin', ORIGINS + [None])
@pytest.mark.parametrize('host', ['localhost:8766', '127.0.0.1:8767'])
def test_desktop_and_trusted_script_access(local_client, origin, host):
    client, calls = local_client
    headers = {'Host': host, **({'Origin': origin} if origin is not None else {})}
    assert client.post('/api/capture/start', headers=headers).status_code == 200
    assert client.post('/api/capture/stop', headers=headers).status_code == 200
    assert client.patch('/api/settings', json=AppSettings().model_dump(), headers=headers).status_code == 200
    assert client.get('/api/lines', headers=headers).json() == []
    with client.websocket_connect('/api/ws', headers=headers) as socket:
        assert socket.receive_json() == {'type': 'snapshot', 'snapshot': {'synthetic': True}}
    assert all(name in calls for name in ['start', 'stop', 'save', 'lines', 'status'])


@pytest.mark.parametrize('origin', BAD_ORIGINS)
def test_rejected_websocket_never_accepts_or_reads_snapshot(local_client, origin):
    client, calls = local_client
    with pytest.raises(WebSocketDisconnect) as closed:
        with client.websocket_connect('/api/ws', headers={'Origin': origin}):
            pytest.fail('Untrusted WebSocket was accepted')
    assert closed.value.code == 1008
    assert calls == []
    assert api.runtime.hub.clients == set()


@pytest.mark.parametrize('method,path,body', [
    ('POST', '/api/capture/start', None), ('POST', '/api/capture/stop', None),
    ('PATCH', '/api/settings', AppSettings().model_dump()),
    ('PATCH', '/api/lines/1/favorite', {'favorite': True}),
    ('POST', '/api/ingest', {'text': 'Synthetic caption'}),
    ('POST', '/api/textmaps/update', None), ('POST', '/api/hito/update', None),
    ('POST', '/api/games/zzz/update', None), ('POST', '/api/updates/check', None),
    ('POST', '/api/runtime/quiesce', None), ('POST', '/api/runtime/activate', {'running': True}),
    ('POST', '/api/setup/complete', {'auto_start': True}),
    ('POST', '/api/lexirise/accounts/select', {'id': 'synthetic'}),
    ('PATCH', '/api/lexirise/settings', {}), ('POST', '/api/lexirise/decks', {'game': 'zzz', 'create': True}),
    ('POST', '/api/lines/1/lexirise', {}),
])
@pytest.mark.parametrize('origin', BAD_ORIGINS)
def test_rejected_http_never_dispatches_mutations(local_client, method, path, body, origin):
    client, calls = local_client
    response = client.request(method, path, json=body,
                              headers={'Origin': origin, 'X-Proxy-Transcript': 'lexirise'})
    assert response.status_code == 403
    assert calls == []


@pytest.mark.parametrize('site', ['same-origin', 'same-site', 'none', None])
def test_browser_media_without_origin_allowed_unless_cross_site(local_client, site):
    client, calls = local_client
    headers = {'Sec-Fetch-Site': site} if site else {}
    assert client.get('/api/lines', headers=headers).json() == []
    assert calls == ['lines']


@pytest.mark.parametrize('site', ['cross-site', 'Cross-Site', 'unknown', ''])
def test_cross_site_request_without_origin_never_dispatches(local_client, site):
    client, calls = local_client
    headers = {'Sec-Fetch-Site': site}
    assert client.get('/api/lines', headers=headers).status_code == 403
    assert client.get('/api/capture/preview.jpg', headers=headers).status_code == 403
    assert client.get('/api/lines/1/reading/lookup?start=0', headers=headers).status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/ws', headers=headers):
            pytest.fail('Cross-site WebSocket was accepted')
    assert calls == []


@pytest.mark.parametrize('origin', ORIGINS)
def test_companion_cross_site_media_with_origin_allowed(local_client, origin):
    client, calls = local_client
    # localhost:3000 loading 127.0.0.1:8766 is cross-site but carries Origin.
    response = client.get('/api/lines', headers={'Origin': origin, 'Sec-Fetch-Site': 'cross-site'})
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    assert calls == ['lines']


def test_duplicate_fetch_site_without_origin_rejected(local_client):
    _, calls = local_client
    assert_raw_denial([(b'host', b'127.0.0.1:8766'), (b'sec-fetch-site', b'same-site'),
                       (b'sec-fetch-site', b'same-site')])
    assert calls == []


@pytest.mark.parametrize('host', BAD_HOSTS)
def test_wrong_or_malformed_host_rejected_for_http_and_websocket(local_client, host):
    client, calls = local_client
    headers = {'Host': host, 'Origin': ORIGINS[0]}
    assert client.post('/api/capture/start', headers=headers).status_code == 403
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/ws', headers=headers):
            pytest.fail('Wrong Host was accepted')
    assert calls == []


@pytest.mark.parametrize('header', ['host', 'origin'])
def test_duplicate_security_headers_are_rejected(local_client, header):
    _, calls = local_client
    headers = [(b'host', b'127.0.0.1:8766'), (b'origin', ORIGINS[0].encode()),
               (header.encode(), b'127.0.0.1:8766' if header == 'host' else ORIGINS[0].encode())]
    assert_raw_denial(headers)
    assert calls == []


def test_missing_host_rejected_before_dispatch(local_client):
    _, calls = local_client
    assert_raw_denial([])
    assert calls == []


def assert_raw_denial(headers):
    # TestClient supplies a missing Host and coalesces duplicates. Feed the
    # real FastAPI ASGI app raw scopes to preserve these server inputs.
    async def check(kind):
        messages = []
        async def receive():
            return {'type': 'websocket.connect'} if kind == 'websocket' else {'type': 'http.request', 'body': b''}
        async def send(message):
            messages.append(message)
        await api.app({'type': kind, 'method': 'POST', 'scheme': 'http', 'server': ('127.0.0.1', 8766),
                       'path': '/api/ws' if kind == 'websocket' else '/api/capture/start',
                       'query_string': b'', 'headers': headers}, receive, send)
        if kind == 'websocket':
            assert messages == [{'type': 'websocket.close', 'code': 1008}]
        else:
            assert messages[0]['type'] == 'http.response.start' and messages[0]['status'] == 403
    for kind in ['http', 'websocket']:
        asyncio.run(check(kind))


@pytest.mark.parametrize('origin', ORIGINS)
def test_preflight_keeps_desktop_headers_and_rejects_unknown_origin(local_client, origin):
    client, calls = local_client
    headers = {'Origin': origin, 'Access-Control-Request-Method': 'PATCH',
               'Access-Control-Request-Headers': 'content-type,x-proxy-transcript,x-proxy-transcript-account'}
    response = client.options('/api/settings', headers=headers)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == origin
    assert 'x-proxy-transcript-account' in response.headers['access-control-allow-headers']
    assert client.options('/api/settings', headers={**headers, 'Origin': 'https://example.test'}).status_code == 403
    assert client.options('/api/settings', headers={**headers, 'Host': 'example.test'}).status_code == 403
    assert calls == []

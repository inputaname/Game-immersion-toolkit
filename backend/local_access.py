"""PC companion access matrix (HTTP and WebSocket, checked before dispatch).

Host                              Origin                              Result
localhost / 127.0.0.1, valid port   http://localhost:3000 or :3001      allow
localhost / 127.0.0.1, valid port   http://127.0.0.1:3000 or :3001      allow
localhost / 127.0.0.1, valid port   absent, no Sec-Fetch-Site           allow scripts
localhost / 127.0.0.1, valid port   absent, Sec-Fetch-Site not cross    allow
localhost / 127.0.0.1, valid port   absent, cross-site or duplicated    deny
localhost / 127.0.0.1, valid port   null, empty, unknown, malformed     deny
localhost / 127.0.0.1, valid port   localhost lookalike / extra Origin deny
other, absent, malformed Host      any                                 deny

Missing Origin explicitly supports trusted non-browser clients on the PC,
including installer status and updater capture fallback requests. It is not
an authentication mechanism for untrusted local programs. Browsers omit
Origin for image, media and script GETs but send Sec-Fetch-Site, so a
cross-site page cannot trigger reading lookups or load captures that way.
The desktop frontend loads media with crossorigin so these carry Origin.
Existing setup, Lexirise and updater action headers still apply, with or
without Origin.
Browser origins stay restricted to the existing desktop frontend ports;
backend ports may vary while the updater prepares a replacement runtime.
The same checks precede CORS preflight, HTTP handlers and WebSocket accept,
so rejected requests cannot capture, read snapshots or mutate local data.
"""
import re

from starlette.responses import JSONResponse


COMPANION_ORIGINS = frozenset(f'http://{host}:{port}'
                              for host in ('localhost', '127.0.0.1') for port in (3000, 3001))
_HOST = re.compile(r'(?:localhost|127\.0\.0\.1)(?::([0-9]{1,5}))?', re.IGNORECASE)


def local_access_allowed(headers):
    """Inspect raw headers so duplicates and malformed ports fail closed."""
    hosts = [value.decode('latin-1') for name, value in headers if name.lower() == b'host']
    origins = [value.decode('latin-1') for name, value in headers if name.lower() == b'origin']
    sites = [value.decode('latin-1') for name, value in headers if name.lower() == b'sec-fetch-site']
    if len(hosts) != 1 or (host := _HOST.fullmatch(hosts[0])) is None:
        return False
    if host[1] is not None and not 1 <= int(host[1]) <= 65535:
        return False
    if origins:
        return len(origins) == 1 and origins[0] in COMPANION_ORIGINS
    return not sites or (len(sites) == 1 and sites[0] in {'same-origin', 'same-site', 'none'})


class LocalAccessMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] in {'http', 'websocket'} and not local_access_allowed(scope.get('headers', [])):
            if scope['type'] == 'websocket':
                await send({'type': 'websocket.close', 'code': 1008})
            else:
                await JSONResponse({'detail': 'Use the local companion on this PC.'}, status_code=403)(scope, receive, send)
            return
        await self.app(scope, receive, send)

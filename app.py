#!/usr/bin/env python3
"""Local server for the knitting row tracker.

Serves the PWA from this folder and exposes POST /api/parse which turns an
uploaded PDF pattern into row JSON. Uses only the Python standard library
plus pypdf.

Run:  python3 app.py           -> http://127.0.0.1:8124
"""
import base64, json, os, sys, tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'pattern-extract'))
from parse_pattern import parse  # noqa: E402

PORT = int(os.environ.get('PORT', '8124'))
MIME = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript',
        '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml',
        '.webmanifest': 'application/manifest+json', '.png': 'image/png'}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def _send(self, code, body, ctype='application/json', extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        elif isinstance(body, str):
            body = body.encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b'', extra={'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                                    'Access-Control-Allow-Headers': 'Content-Type'})

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            path = '/index.html'
        fp = os.path.join(HERE, path.lstrip('/'))
        if not os.path.isfile(fp) or not os.path.abspath(fp).startswith(HERE):
            return self._send(404, {'error': 'not found'})
        ext = os.path.splitext(fp)[1]
        with open(fp, 'rb') as f:
            self._send(200, f.read(), MIME.get(ext, 'application/octet-stream'))

    def do_POST(self):
        if self.path not in ('/api/parse', '/api/sizes'):
            return self._send(404, {'error': 'not found'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            data = json.loads(self.rfile.read(length).decode('utf-8'))
            pdf = base64.b64decode(data['pdf'])
            if not pdf.lower().startswith(b'%pdf'):
                return self._send(400, {'error': 'That file is not a PDF.'})
            f = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            try:
                f.write(pdf); f.close()
                if self.path == '/api/sizes':
                    from parse_pattern import extract_text, CASTON_RE, CHAIN
                    import re
                    t = extract_text(f.name)
                    m = CASTON_RE.search(t)
                    count = 1
                    if m:
                        first = CHAIN.search(m.group(1))
                        if first:
                            count = max(1, len(re.findall(r'\d+', first.group(0))))
                    return self._send(200, {'count': count})
                size = int(data.get('size', 0))
                result = parse(f.name, size)
            finally:
                os.unlink(f.name)
            self._send(200, result)
        except Exception as e:  # noqa: BLE001
            self._send(400, {'error': 'Could not read PDF: %s' % e})


if __name__ == '__main__':
    print('Knitting tracker running at http://127.0.0.1:%d' % PORT)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()

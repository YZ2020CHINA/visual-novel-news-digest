"""Local-only Project Blocks server. Python standard library, no installation."""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import argparse
import hashlib
import json
import os
import threading
import webbrowser

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data/project.json'
LOCK = threading.Lock()
MAX_BYTES = 16 * 1024 * 1024


def validate(p):
    if not isinstance(p, dict) or not isinstance(p.get('nodes'), list):
        raise ValueError('工程必须包含 nodes 数组')
    nodes = p['nodes']
    if not isinstance(p.get('title', ''), str):
        raise ValueError('工程标题必须是字符串')
    for field in ('groups', 'stickyNotes', 'customRoutes'):
        if not isinstance(p.get(field, []), list):
            raise ValueError(f'{field} 必须是数组')
    viewport = p.get('viewport', {})
    if not isinstance(viewport, dict) or any(not isinstance(viewport.get(k), (int, float)) for k in ('x', 'y', 'scale')) or not 0 < viewport['scale'] <= 10:
        raise ValueError('视口参数无效')
    if len(nodes) > 2000:
        raise ValueError('单个工程最多 2000 张卡片')
    ids = [n.get('id') for n in nodes if isinstance(n, dict)]
    if len(ids) != len(nodes) or any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('卡片 ID 必须是非空且唯一的字符串')
    known = set(ids)
    for n in nodes:
        for axis in ('x', 'y'):
            if not isinstance(n.get(axis), (int, float)) or not (-1000000 <= n[axis] <= 1000000):
                raise ValueError('卡片坐标无效')
        if not isinstance(n.get('choices', []), list):
            raise ValueError('输出关系必须是数组')
        for c in n.get('choices', []):
            if not isinstance(c, dict) or not isinstance(c.get('id'), str):
                raise ValueError('输出关系需要 ID')
            if c.get('target') and c['target'] not in known:
                raise ValueError('关系指向不存在的卡片')
        if n.get('defaultNext') and n['defaultNext'] not in known:
            raise ValueError('关系指向不存在的卡片')
    return p


def read_data():
    raw = DATA.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'app'), **kwargs)

    def json_response(self, status, value):
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/api/info':
            return self.json_response(200, {'app': 'project-blocks', 'dataFile': str(DATA), 'projectRoot': str(DATA.parent.parent.parent if DATA.parent.name == 'data' else DATA.parent)})
        if self.path == '/api/project':
            try:
                with LOCK:
                    p, rev = read_data()
                self.json_response(200, {'project': validate(p), 'revision': rev, 'dataFile': str(DATA)})
            except (ValueError, OSError) as e:
                self.json_response(422, {'error': str(e)})
        elif self.path.startswith('/api/'):
            self.json_response(404, {'error': '接口不存在'})
        else:
            super().do_GET()

    def do_PUT(self):
        # Same-origin JSON only; bind loopback and reject browser cross-origin writes.
        if self.path != '/api/project':
            return self.json_response(404, {'error': '接口不存在'})
        origin = self.headers.get('Origin')
        if origin and origin not in {f'http://127.0.0.1:{self.server.server_port}', f'http://localhost:{self.server.server_port}'}:
            return self.json_response(403, {'error': '仅接受本地页面保存'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BYTES:
                return self.json_response(413, {'error': '文件为空或超过 16 MB'})
            body = json.loads(self.rfile.read(length))
            p = validate(body.get('project'))
            with LOCK:
                _, revision = read_data()
                if body.get('revision') != revision:
                    return self.json_response(409, {'error': '磁盘工程已更新，请先处理版本冲突'})
                raw = json.dumps(p, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
                DATA.with_suffix('.backup.json').write_bytes(DATA.read_bytes())
                temp = DATA.with_suffix('.tmp')
                temp.write_bytes(raw)
                os.replace(temp, DATA)
                revision = hashlib.sha256(raw).hexdigest()
            self.json_response(200, {'revision': revision})
        except (ValueError, TypeError, OSError, AttributeError) as e:
            self.json_response(422, {'error': str(e)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--data', type=Path, default=DATA, help='Project JSON path')
    args = parser.parse_args()
    DATA = args.data.resolve()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    url = f'http://127.0.0.1:{args.port}'
    print(f'Project Blocks: {url}\nData: {DATA}', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

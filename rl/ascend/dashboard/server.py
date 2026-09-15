"""Portable observation dashboard. Bind localhost; reach it through an SSH tunnel."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import zipfile
from urllib.parse import parse_qs, urlparse
from generalist_data import GeneralistData, read_json
import resource_control

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
EXAM = ROOT/('exam-search' if (ROOT/'exam-search').is_dir() else 'exam_search')
ARENA = EXAM/'runtime/arena'
DATA = ARENA/'_vendor/gakumas_tools/packages/gakumas-data/json'
if not DATA.is_dir():
    DATA = ARENA/'gakumas_arena/_vendor/gakumas_tools/packages/gakumas-data/json'
CARDS = {x['id']: x for x in read_json(DATA/'skill_cards.json', [])}
DRINKS = {x['id']: x for x in read_json(DATA/'p_drinks.json', [])}
CUSTOMS = {str(x['id']): x for x in read_json(DATA/'customizations.json', [])}
IMAGES = HERE/'assets'
IMAGE_ARCHIVE = HERE/'assets.zip'
with zipfile.ZipFile(IMAGE_ARCHIVE) if IMAGE_ARCHIVE.exists() else __import__('contextlib').nullcontext() as archive:
    IMAGE_NAMES = set(archive.namelist()) if archive else set()
STATIC = {'generalist.html', 'generalist.js', 'generalist.css', 'resources.js',
          'search-panel.js', 'style.css', 'draft.css', 'logs.css'}


def icon(kind, identifier):
    keys = [f'{identifier}_8', f'{identifier}_6', str(identifier)] if kind == 'skillCards' else [str(identifier)]
    for key in keys:
        relative = f'{kind}/icons/{key}.png'
        if relative in IMAGE_NAMES or (IMAGES/relative).is_file():
            return '/assets/'+relative
    return None


def card(row):
    definition = CARDS.get(row['definition_id'], {})
    return {'uid': row['instance_id'], 'id': row['definition_id'],
            'name': definition.get('name', str(row['definition_id'])), 'rarity': definition.get('rarity'),
            'icon': icon('skillCards', row['definition_id']),
            'customizations': row.get('customizations', {}), 'growth': row.get('growth', {}),
            'guidance_names': [f"{CUSTOMS.get(k, {}).get('name', k)} Lv.{v}" for k,v in row.get('customizations', {}).items()],
            'effective': definition}


def drink(identifier):
    return {'id': identifier, 'name': DRINKS.get(identifier, {}).get('name', str(identifier)),
            'icon': icon('pDrinks', identifier)}


def make_server(run, port=8900):
    run = Path(run).resolve()
    if not run.is_dir():
        raise ValueError('Run directory does not exist; start training first')
    manifest = read_json(run/'manifest.json')
    if manifest and manifest.get('config', {}).get('training_stage') != 'joint_build_and_public_history_mcts_exam':
        raise ValueError('This dashboard expects a joint search training run')
    abilities = {}
    for profile in manifest.get('profiles', []):
        for value in profile.get('spec', {}).get('memory', {}).get('abilities', []):
            abilities[value['id']] = value
    def memory(identifier):
        value = abilities.get(identifier, {})
        return {'id': identifier, 'name': value.get('name', value.get('target_card_name', identifier)),
                'description': value.get('description', ''), 'icon': None}
    data = GeneralistData(ROOT, card=card, drink=drink, memory=memory,
                          custom_names={k:v['name'] for k,v in CUSTOMS.items()}, run_dir=run)

    class Handler(BaseHTTPRequestHandler):
        def send(self, value, status=200, kind='application/json; charset=utf-8'):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.path != '/api/generalist/resources':
                return self.send({'error': 'Not found'}, 404)
            host = self.headers.get('Host', '')
            allowed = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if host not in allowed or self.headers.get('Origin', 'http://'+host) != 'http://'+host:
                return self.send({'error': 'Use the localhost dashboard'}, 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('Expected a small JSON request')
                self.send(resource_control.request(run, json.loads(self.rfile.read(length))))
            except (ValueError, TypeError, OSError) as error:
                self.send({'error': str(error)}, 400)

        def do_GET(self):
            try:
                route = urlparse(self.path)
                query = parse_qs(route.query)
                one = lambda key, default='': query.get(key, [default])[0]
                if route.path == '/health':
                    return self.send({'ok': True, 'pid': os.getpid(), 'run': str(run)})
                if route.path == '/api/generalist':
                    return self.send(data.state())
                if route.path == '/api/generalist/resources':
                    return self.send(resource_control.state(run))
                if route.path == '/api/generalist/episodes':
                    return self.send(data.episodes(one('mode', 'train')))
                if route.path == '/api/generalist/episode':
                    return self.send(data.episode(one('mode', 'train'), one('file'), int(one('seed')), replay=one('replay', '1') != '0'))
                if route.path == '/api/generalist/logs':
                    return self.send(data.logs(one('source', 'progress')))
                if route.path.startswith('/assets/'):
                    relative = route.path[len('/assets/'):]
                    if relative in IMAGE_NAMES:
                        with zipfile.ZipFile(IMAGE_ARCHIVE) as archive:
                            return self.send(archive.read(relative), kind='image/png')
                    path = (IMAGES/relative).resolve()
                    if not path.is_relative_to(IMAGES.resolve()) or path.suffix != '.png':
                        return self.send({'error': 'Not found'}, 404)
                else:
                    name = 'generalist.html' if route.path == '/' else route.path.lstrip('/')
                    if name not in STATIC:
                        return self.send({'error': 'Not found'}, 404)
                    path = HERE/name
                if not path.is_file():
                    return self.send({'error': 'Not found'}, 404)
                return self.send(path.read_bytes(), kind=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            except (ValueError, TypeError, KeyError, OSError) as error:
                self.send({'error': str(error)}, 400)

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8900)
    args = parser.parse_args()
    with make_server(args.run, args.port) as server:
        print(f'Training dashboard: http://127.0.0.1:{server.server_port}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

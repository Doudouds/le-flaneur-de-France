#!/usr/bin/env python3
"""PC-only map for reviewing the audit. No catalogue or Android changes."""
import argparse
import csv
import datetime
import gzip
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import math
import os
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.parse import urlsplit
import webbrowser
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).with_name('coordinate_review')
DECISIONS = {'a_verifier', 'bon', 'mauvais'}
UNCHANGED = object()


def valid_position(value):
    return isinstance(value, dict) and all(type(value.get(k)) in (int, float) and math.isfinite(value[k])
        and -limit <= value[k] <= limit for k, limit in (('latitude', 90), ('longitude', 180)))


def snapshot(review, action):
    return {k: v for k, v in review.items() if k != 'history'} | {'action': action}


class ReviewStore:
    def __init__(self, audit, path):
        self.path = path
        self.lock = threading.Lock()
        with audit.open(encoding='utf-8-sig', newline='') as handle:
            self.rows = list(csv.DictReader(handle, delimiter=';'))
        self.by_ref = {row['reference']: row for row in self.rows}
        if len(self.by_ref) != len(self.rows):
            raise ValueError('Duplicate references in audit')
        if not self.rows:
            raise ValueError('The audit is empty')
        for row in self.rows:
            row['latitude'] = float(row['latitude'])
            row['longitude'] = float(row['longitude'])
        self.read()  # Fail visibly on a damaged review file; never replace it.

    def read(self):
        if not self.path.exists():
            return {'version': 1, 'reviews': {}}
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if data.get('version') != 1 or not isinstance(data.get('reviews'), dict):
            raise ValueError('Unsupported review file')
        if any(not isinstance(r, dict) or r.get('decision') not in DECISIONS or not isinstance(r.get('note'), str)
               for r in data['reviews'].values()):
            raise ValueError('Invalid saved review')
        if any((r.get('correction') is not None and not valid_position(r['correction']))
               or not isinstance(r.get('history', []), list) for r in data['reviews'].values()):
            raise ValueError('Invalid saved correction or history')
        return data

    def save(self, ref, decision=UNCHANGED, note=UNCHANGED, correction=UNCHANGED):
        if (ref not in self.by_ref or (decision is not UNCHANGED and decision not in DECISIONS)
                or (note is not UNCHANGED and (not isinstance(note, str) or len(note) > 5000))
                or (correction is not UNCHANGED and correction is not None and not valid_position(correction))):
            raise ValueError('Décision, référence ou commentaire invalide.')
        with self.lock:
            data = self.read()
            row = self.by_ref[ref]
            previous = data['reviews'].get(ref, {})
            now = datetime.datetime.now(datetime.timezone.utc).isoformat()
            updated = dict(previous, decision=previous.get('decision', 'a_verifier') if decision is UNCHANGED else decision,
                note=previous.get('note', '') if note is UNCHANGED else note,
                latitude=row['latitude'], longitude=row['longitude'])
            action = 'decision_ou_commentaire'
            if correction is not UNCHANGED:
                action = 'position_corrigee' if correction is not None else 'position_retablie'
                old = previous.get('correction')
                if correction is None:
                    updated['correction'] = None
                elif old is None or any(old[k] != correction[k] for k in ('latitude', 'longitude')):
                    updated['correction'] = {k: correction[k] for k in ('latitude', 'longitude')} | {'updated_at': now}
            if updated == previous:
                return previous  # Selecting the next place must not duplicate the history.
            history = list(previous.get('history', []))
            if previous and not history:
                history.append(snapshot(previous, 'etat_initial_conserve'))
            updated['updated_at'] = now
            history.append(snapshot(updated, action))
            updated['history'] = history
            data['reviews'][ref] = updated
            self.path.parent.mkdir(parents=True, exist_ok=True)
            if self.path.exists():
                # Exact pre-write copy, including old notes and unknown future fields.
                folder = self.path.parent/'coordinate_review_backups'
                folder.mkdir(exist_ok=True)
                stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
                backup = folder/(self.path.stem+'-'+stamp+'-'+secrets.token_hex(3)+'.json')
                with backup.open('xb') as handle:
                    handle.write(self.path.read_bytes())
                    handle.flush()
                    os.fsync(handle.fileno())
            temporary = None
            try:
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=self.path.parent,
                                                 prefix=self.path.name, suffix='.tmp', delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump(data, handle, ensure_ascii=False, indent=2)
                    handle.flush()
                    os.fsync(handle.fileno())
                temporary.replace(self.path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return data['reviews'][ref]

    def contours(self, cache):
        wanted = {code for row in self.rows for code in row.get('codes_controles', '').split(';') if code}
        found = {}
        for kind in ('communes', 'communes-associees-deleguees'):
            path = cache/(kind+'-100m.geojson.gz')
            if path.exists():
                for feature in json.loads(gzip.decompress(path.read_bytes()))['features']:
                    code = feature['properties']['code']
                    if code in wanted and feature.get('geometry'):
                        found.setdefault(code, feature)
        return found

    def export_csv(self):
        reviews = self.read()['reviews']
        out = io.StringIO(newline='')
        fields = list(self.rows[0]) + ['decision', 'commentaire', 'date_decision', 'position_modifiee_depuis_decision',
            'latitude_corrigee', 'longitude_corrigee', 'date_correction', 'nombre_entrees_historique']
        writer = csv.DictWriter(out, fieldnames=fields, delimiter=';')
        writer.writeheader()
        for row in self.rows:
            review = reviews.get(row['reference'], {})
            changed = bool(review) and (review.get('latitude'), review.get('longitude')) != (row['latitude'], row['longitude'])
            correction = review.get('correction') or {}
            item = dict(row, decision=review.get('decision', 'a_verifier'), commentaire=review.get('note', ''),
                        date_decision=review.get('updated_at', ''), position_modifiee_depuis_decision=changed,
                        latitude_corrigee=correction.get('latitude', ''), longitude_corrigee=correction.get('longitude', ''),
                        date_correction=correction.get('updated_at', ''), nombre_entrees_historique=len(review.get('history', [])))
            # Do not turn a personal note or source label into an Excel formula.
            for key, value in item.items():
                if isinstance(value, str) and value.startswith(('=', '+', '-', '@')):
                    item[key] = "'"+value
            writer.writerow(item)
        return ('\ufeff'+out.getvalue()).encode('utf-8')


class ReviewServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, store, cache):
        super().__init__(('127.0.0.1', port), Handler)
        self.store = store
        self.token = secrets.token_urlsafe(32)
        self.boundaries = store.contours(cache)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send(self, status, body, content_type='application/json; charset=utf-8', filename=None):
        if not isinstance(body, bytes):
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if filename:
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(body)

    def local_request(self, mutation=False):
        port = self.server.server_port
        allowed = {f'127.0.0.1:{port}', f'localhost:{port}'}
        if self.headers.get('Host') not in allowed:
            self.send(403, {'error': 'Hôte non autorisé.'})
            return False
        if mutation and (self.headers.get('Origin') not in {f'http://{host}' for host in allowed}
                         or self.headers.get('X-Review-Token') != self.server.token):
            self.send(403, {'error': 'Requête locale non autorisée.'})
            return False
        return True

    def do_GET(self):
        if not self.local_request():
            return
        route = urlsplit(self.path).path
        try:
            if route == '/api/health':
                self.send(200, {'app': 'flaneur-coordinate-review'})
            elif route == '/api/data':
                self.send(200, {'monuments': self.server.store.rows, 'reviews': self.server.store.read()['reviews'],
                                'token': self.server.token, 'capabilities': {'corrections': True, 'history': True}})
            elif route.startswith('/api/contours/'):
                row = self.server.store.by_ref.get(route.rsplit('/', 1)[1])
                if row is None:
                    self.send(404, {'error': 'Référence inconnue.'})
                    return
                self.send(200, {'type': 'FeatureCollection', 'features': [self.server.boundaries[c]
                    for c in row.get('codes_controles', '').split(';') if c in self.server.boundaries]})
            elif route == '/api/export.csv':
                self.send(200, self.server.store.export_csv(), 'text/csv; charset=utf-8', 'verification-positions.csv')
            elif route == '/api/export.json':
                self.send(200, json.dumps(self.server.store.read(), ensure_ascii=False, indent=2).encode('utf-8'),
                          filename='verification-positions.json')
            else:
                relative = 'index.html' if route == '/' else route.lstrip('/')
                path = (STATIC/relative).resolve()
                if not path.is_relative_to(STATIC.resolve()) or not path.is_file():
                    self.send(404, {'error': 'Fichier introuvable.'})
                    return
                types = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                         '.css': 'text/css; charset=utf-8', '.png': 'image/png'}
                self.send(200, path.read_bytes(), types.get(path.suffix, 'text/plain; charset=utf-8'))
        except (OSError, ValueError, KeyError):
            self.send(500, {'error': 'Lecture impossible. Le fichier de décisions a été conservé.'})

    def do_PUT(self):
        if not self.local_request(mutation=True):
            return
        route = urlsplit(self.path).path
        if not route.startswith(('/api/reviews/', '/api/corrections/')):
            self.send(404, {'error': 'Route inconnue.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 30000:
                raise ValueError('Requête trop volumineuse.')
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError('Requête invalide.')
            if route.startswith('/api/corrections/'):
                if 'correction' not in payload:
                    raise ValueError('Position manquante.')
                review = self.server.store.save(route.rsplit('/', 1)[1],
                    note=payload.get('note', UNCHANGED), correction=payload['correction'])
            else:
                review = self.server.store.save(route.rsplit('/', 1)[1], payload.get('decision'), payload.get('note', ''))
            self.send(200, review)
        except (ValueError, TypeError):
            self.send(400, {'error': 'Décision ou commentaire invalide.'})
        except OSError:
            self.send(500, {'error': 'Enregistrement impossible. Réessayez avant de quitter.'})

    def do_POST(self):
        if not self.local_request(mutation=True):
            return
        if self.path != '/api/stop':
            self.send(404, {'error': 'Route inconnue.'})
            return
        self.send(200, {'stopped': True})
        threading.Thread(target=self.server.shutdown, daemon=True).start()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--audit', type=Path, default=ROOT/'docs/coordinate-audit.csv')
    parser.add_argument('--reviews', type=Path, default=ROOT/'data/coordinate_reviews.json')
    parser.add_argument('--cache', type=Path, default=ROOT/'data/geo_audit_cache')
    parser.add_argument('--open', action='store_true', help='Open the PC browser')
    args = parser.parse_args()
    store = ReviewStore(args.audit, args.reviews)
    try:
        server = ReviewServer(args.port, store, args.cache)
    except OSError:
        if args.open:
            try:
                with urlopen(f'http://127.0.0.1:{args.port}/api/health', timeout=2) as response:
                    if json.load(response).get('app') == 'flaneur-coordinate-review':
                        webbrowser.open(f'http://127.0.0.1:{args.port}/')
                        return
            except (OSError, ValueError):
                pass
        raise
    url = f'http://127.0.0.1:{server.server_port}/'
    print(f'Carte locale : {url}\nDécisions : {args.reviews}\nCtrl+C pour arrêter.', flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()

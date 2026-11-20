import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def relative(name):
    path = PurePosixPath(name)
    if path.is_absolute():
        path = path.relative_to('/src')
    if '..' in path.parts or not path.parts:
        raise ValueError(f'Invalid source path: {name}')
    return str(path)


def parse(source, directory):
    files = {p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    python = {p for p in files if p.endswith('.py')}
    if not python:
        raise ValueError('No Python sources in snapshot')
    required = python | {p for p in files if p.endswith(('.sh', '.bash', '.dockerfile')) or Path(p).name in {'Dockerfile', 'compose.yaml', 'compose.yml', 'docker-compose.yml', 'docker-compose.yaml'}}
    manifest = {'source': str(source.resolve()), 'commit': os.getenv('SOURCE_COMMIT'), 'tools': {}, 'findings': []}
    for name in ('semgrep', 'bandit'):
        raw = (directory / f'{name}.json').read_bytes()
        data = json.loads(raw)
        status = int((directory / f'{name}.exit').read_text())
        results = data['results']
        if not isinstance(results, list) or data['errors'] != []:
            raise ValueError(f'{name}: malformed results or scan errors: {data["errors"]}')
        if name == 'semgrep':
            scanned = {relative(p) for p in data['paths']['scanned']}
            if status or data.get('skipped_rules') or data.get('time', {}).get('fixpoint_timeouts'):
                raise ValueError(f'{name}: incomplete scan')
            missing = required - scanned
        else:
            scanned = {relative(p) for p in data['metrics'] if p != '_totals'}
            if status != int(bool(results)) or '_totals' not in data['metrics']:
                raise ValueError(f'{name}: inconsistent status or metrics')
            missing = python - scanned
        if missing or scanned - files:
            raise ValueError(f'{name}: missing targets {sorted(missing)}, unknown targets {sorted(scanned - files)}')
        image, labels = (directory / f'{name}.image').read_text().split(' ', 1)
        labels = json.loads(labels)
        manifest['tools'][name] = {'image': json.loads(image), 'version': labels['scan.version'], 'rules': labels['scan.rules'], 'rules_sha256': labels.get('scan.rules.sha256'), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'scanned': sorted(scanned), 'outside_scan': sorted(files - scanned)}
        for i, hit in enumerate(results, 1):
            if name == 'semgrep':
                extra = hit['extra']
                path, line, rule = hit['path'], hit['start']['line'], hit['check_id']
                text, severity, confidence = extra['message'], extra['severity'], extra.get('metadata', {}).get('confidence')
            else:
                path, line, rule = hit['filename'], hit['line_number'], hit['test_id']
                text, severity, confidence = hit['issue_text'], hit['issue_severity'], hit['issue_confidence']
            path = relative(path)
            if path not in scanned or not isinstance(line, int) or line < 1 or not rule or not text:
                raise ValueError(f'{name}: invalid finding {i}')
            manifest['findings'].append({'id': f'{name}:{i}', 'tool': name, 'file': path, 'line': line, 'rule': rule, 'details': text, 'severity': severity, 'confidence': confidence})
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source', type=Path)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    record = parse(args.source, args.directory)
    (args.directory / 'scan.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

import argparse
import hashlib
import json
from collections import Counter
from html import escape
from pathlib import Path


PRIORITIES = {'high': 'Высокий', 'medium': 'Средний', 'low': 'Низкий', 'fp': 'Ложное срабатывание'}
TOOLS = {'semgrep': 'Semgrep', 'bandit': 'Bandit'}
COLUMNS = ['Файл', 'Строка', 'Тип ошибки', 'Подробности']


def row(values):
    return '| ' + ' | '.join(escape(' '.join(str(v).split()), quote=False).replace('\\', '\\\\').replace('|', '\\|') for v in values) + ' |'


def table(columns, rows):
    return [row(columns), row(['---'] * len(columns)), *[row(r) for r in rows], '']


def section(directory):
    data = json.loads((directory / 'scan.json').read_text())
    groups = json.loads((directory / 'triage.json').read_text())
    hits = {h['id']: h for h in data['findings']}
    refs = Counter(k for g in groups for k in g['ids'])
    if refs != Counter(hits.keys()) or any(not g['ids'] or not g['reason'].strip() or not g['type'].strip() for g in groups):
        raise ValueError(f'{directory}: triage must cover each finding exactly once, with a reason')
    title = directory.name
    lines = [f'## {title}', '']
    if data['commit']:
        lines += [f'Ревизия исходников: `{data["commit"]}`.', '']
    counts = {}
    for tool, pretty in TOOLS.items():
        info = data['tools'][tool]
        raw = (directory / f'{tool}.json').read_bytes()
        found = sorted((h for h in hits.values() if h['tool'] == tool), key=lambda h: (h['file'], h['line'], h['rule']))
        if hashlib.sha256(raw).hexdigest() != info['raw_sha256'] or len(json.loads(raw)['results']) != len(found):
            raise ValueError(f'{title}: normalized results do not match {tool}.json')
        counts[tool] = len(found)
        lines += [f'### {pretty} {info["version"]}', '', f'Файлов в отчете: {len(info["scanned"])}. Срабатываний: {len(found)}.', '']
        rows = []
        for h in found:
            confidence = f'; уверенность: {h["confidence"]}' if h['confidence'] else ''
            rows.append([h['file'], h['line'], h['rule'], f'{h["details"]} (уровень: {h["severity"]}{confidence})'])
        lines += table(COLUMNS, rows)
    lines += ['### Сводная таблица', '']
    summary = []
    for group in sorted(groups, key=lambda g: (list(PRIORITIES).index(g['priority']), g['ids'])):
        members = [hits[k] for k in group['ids']]
        locations = list(dict.fromkeys((h['file'], h['line']) for h in members))
        tools = '; '.join(f'{TOOLS[h["tool"]]}: {h["rule"]}' for h in members)
        summary.append(['; '.join(f for f, _ in locations), '; '.join(str(n) for _, n in locations), group['type'], group['reason'], tools, PRIORITIES[group['priority']]])
    lines += table(COLUMNS + ['Инструмент(ы) и правило', 'Приоритет / решение'], summary)
    counts['fp'] = sum(g['priority'] == 'fp' for g in groups)
    counts['confirmed'] = len(groups) - counts['fp']
    counts['infra'] = sum(g['priority'] != 'fp' and all(not hits[k]['file'].endswith('.py') for k in g['ids']) for g in groups)
    lines += [f'Подтвержденных проблем: {counts["confirmed"]}; из них вне Python: {counts["infra"]}. Ложных срабатываний после объединения дублей: {counts["fp"]}.', '', 'Числа относятся только к файлам и правилам, вошедшим в проверку.', '']
    return lines, counts, {k: v['image'] for k, v in data['tools'].items()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('directories', type=Path, nargs='+', metavar='REPORT_DIR')
    parser.add_argument('-o', '--output', type=Path, required=True)
    args = parser.parse_args()
    if len(args.directories) not in (1, 2) or len({d.resolve() for d in args.directories}) != len(args.directories):
        parser.error('supply one application or two distinct applications, in comparison order')
    parts = [section(d) for d in args.directories]
    lines = ['# Задание 8. Результаты статического анализа', '']
    for part, _, _ in parts:
        lines.extend(part)
    if len(parts) == 2:
        if parts[0][2] != parts[1][2]:
            parser.error('scan images differ between applications')
        lines += ['## Вывод', '', f'Сравнение {args.directories[0].name} и {args.directories[1].name}:', '']
        for key, label in [('semgrep', 'Срабатывания Semgrep'), ('bandit', 'Срабатывания Bandit'), ('confirmed', 'Подтвержденные проблемы'), ('infra', 'Из них вне Python'), ('fp', 'Ложные срабатывания без дублей')]:
            a, b = parts[0][1][key], parts[1][1][key]
            delta = b - a
            change = f'рост на {delta}' if delta > 0 else f'снижение на {-delta}' if delta < 0 else 'без изменений'
            lines.append(f'- {label}: {a} и {b} ({change}).')
    args.output.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')

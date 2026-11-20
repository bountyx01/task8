import ipaddress
from datetime import datetime

from psycopg import sql

SCHEMA = {
    "sectors": {"id": "int", "name": "text", "industry": "text", "description": "text"},
    "hosts": {"id": "int", "sector_id": "int", "hostname": "text", "ip": "inet", "os": "text", "is_critical": "bool"},
    "teams": {"id": "int", "name": "text", "country": "text", "members": "int", "score": "int"},
    "reports": {
        "id": "int", "team_id": "int", "host_id": "int", "event": "text",
        "severity": "text", "status": "text", "points": "int", "submitted_at": "timestamp",
    },
}

CHILDREN = {
    "sectors": ("hosts", "sector_id"),
    "hosts": ("reports", "host_id"),
    "teams": ("reports", "team_id"),
}

REQUIRED = {
    "sectors": ("name", "industry"),
    "hosts": ("sector_id", "hostname", "ip", "os"),
    "teams": ("name", "country", "members"),
    "reports": ("team_id", "host_id", "event", "severity"),
}

OPTIONS = {
    "is_critical": ("true", "false"),
    "severity": ("low", "medium", "high", "critical"),
    "status": ("submitted", "accepted", "rejected"),
}

HINTS = {
    "int": "целое число", "text": "текст", "bool": "true или false",
    "inet": "IP-адрес", "timestamp": "дата и время вида 2026-10-08 14:30",
}


def as_bool(raw):
    if raw.lower() in ("true", "да", "1", "yes"):
        return True
    if raw.lower() in ("false", "нет", "0", "no"):
        return False
    raise ValueError(raw)


PARSERS = {
    "int": int, "text": str, "bool": as_bool, "inet": ipaddress.ip_address, "timestamp": datetime.fromisoformat,
}


def spec(name):
    if name not in SCHEMA:
        raise ValueError("нет такой таблицы")
    return SCHEMA[name]


def editable(name):
    return [field for field in spec(name) if field != "id"]


def column(name, field, writable=False):
    if field not in spec(name):
        raise ValueError(f"в таблице {name} нет такой колонки")
    if writable and field == "id":
        raise ValueError("колонку id менять нельзя")
    return sql.Identifier(field)


def convert(name, field, raw):
    if raw == "":
        return None
    kind = spec(name)[field]
    try:
        return PARSERS[kind](raw)
    except ValueError:
        raise ValueError(f"{field}: ожидается {HINTS[kind]}") from None


def select_rows(conn, name, filters):
    fields = spec(name)
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(name))
    clauses = []
    values = []
    for field, op, raw in filters:
        col = column(name, field)
        if op == "null":
            clauses.append(sql.SQL("{} IS NULL").format(col))
        elif op == "eq":
            clauses.append(sql.SQL("{} = %s").format(col))
            values.append(convert(name, field, raw))
        else:
            raise ValueError("неизвестное условие фильтра")
    if clauses:
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
    return fields, conn.execute(query + sql.SQL(" ORDER BY id"), values).fetchall()


def insert_rows(conn, name, fields, rows):
    names = [column(name, field, writable=True) for field in fields]
    group = sql.SQL("({})").format(sql.SQL(", ").join([sql.Placeholder()] * len(fields)))
    query = sql.SQL("INSERT INTO {} ({}) VALUES {} RETURNING id").format(
        sql.Identifier(name), sql.SQL(", ").join(names), sql.SQL(", ").join([group] * len(rows)),
    )
    values = [convert(name, field, raw) for row in rows for field, raw in zip(fields, row, strict=True)]
    return [row[0] for row in conn.execute(query, values).fetchall()]


def insert_tree(conn, name, fields, child_fields, batch):
    child, link = CHILDREN[name]
    created = []
    with conn.transaction():
        for row, children in batch:
            key, = insert_rows(conn, name, fields, [row])
            ids = []
            if children:
                linked = [[str(key), *values] for values in children]
                ids = insert_rows(conn, child, [link, *child_fields], linked)
            created.append((key, ids))
    return created


def update_row(conn, name, key_raw, changes):
    key = convert(name, "id", key_raw)
    if key is None:
        raise ValueError("нужно значение id")
    assignments = [sql.SQL("{} = %s").format(column(name, field, writable=True)) for field in changes]
    query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(sql.Identifier(name), sql.SQL(", ").join(assignments))
    values = [convert(name, field, raw) for field, raw in changes.items()]
    touched = conn.execute(query, [*values, key]).rowcount
    if not touched:
        raise ValueError(f"в таблице {name} нет записи с id = {key}")
    return touched


def update_rows(conn, name, field, raw, by_field, raws):
    query = sql.SQL("UPDATE {} SET {} = %s WHERE {} = ANY(%s)").format(
        sql.Identifier(name), column(name, field, writable=True), column(name, by_field)
    )
    if not raws:
        raise ValueError("нужно хотя бы одно значение для отбора")
    values = [convert(name, field, raw), [convert(name, by_field, item) for item in raws]]
    return conn.execute(query, values).rowcount

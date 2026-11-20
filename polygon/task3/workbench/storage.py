import ipaddress
from datetime import datetime

from psycopg import sql

SCHEMA = {
    "sectors": {
        "key": "id",
        "fields": {"id": "int", "name": "text", "industry": "text", "description": "text"},
        "children": {"hosts": "sector_id"},
    },
    "hosts": {
        "key": "id",
        "fields": {"id": "int", "sector_id": "int", "hostname": "text", "ip": "inet", "os": "text", "is_critical": "bool"},
        "children": {"reports": "host_id"},
    },
    "teams": {
        "key": "id",
        "fields": {"id": "int", "name": "text", "country": "text", "members": "int", "score": "int"},
        "children": {"reports": "team_id"},
    },
    "reports": {
        "key": "id",
        "fields": {
            "id": "int", "team_id": "int", "host_id": "int", "event": "text",
            "severity": "text", "status": "text", "points": "int", "submitted_at": "timestamp",
        },
        "children": {},
    },
}

HINTS = {
    "int": "целое число",
    "text": "текст",
    "bool": "true или false",
    "inet": "IP-адрес",
    "timestamp": "дата и время вида 2026-10-08 14:30",
}


def as_bool(raw):
    if raw.lower() in ("true", "да", "1", "yes"):
        return True
    if raw.lower() in ("false", "нет", "0", "no"):
        return False
    raise ValueError(raw)


PARSERS = {
    "int": int,
    "text": str,
    "bool": as_bool,
    "inet": ipaddress.ip_address,
    "timestamp": datetime.fromisoformat,
}


def spec(name):
    if name not in SCHEMA:
        raise ValueError(f"нет таблицы {name}")
    return SCHEMA[name]


def editable(name):
    table = spec(name)
    return [field for field in table["fields"] if field != table["key"]]


def child_fields(parent, child):
    link = spec(parent)["children"].get(child)
    if link is None:
        raise ValueError(f"у таблицы {parent} нет дочерней таблицы {child}")
    return [field for field in editable(child) if field != link]


def column(name, field, writable=False):
    table = spec(name)
    if field not in table["fields"]:
        raise ValueError(f"в таблице {name} нет колонки {field}")
    if writable and field == table["key"]:
        raise ValueError(f"колонку {field} менять нельзя")
    return sql.Identifier(field)


def convert(name, field, raw):
    kind = spec(name)["fields"][field]
    if raw == "":
        return None
    try:
        return PARSERS[kind](raw)
    except ValueError:
        raise ValueError(f"{field}: ожидается {HINTS[kind]}, получено {raw!r}") from None


def select_rows(conn, name, filters):
    spec(name)
    query = sql.SQL("SELECT * FROM {}").format(sql.Identifier(name))
    values = []
    if filters:
        clauses = []
        for field, raw in filters:
            clauses.append(sql.SQL("{} = %s").format(column(name, field)))
            values.append(convert(name, field, raw))
        query += sql.SQL(" WHERE ") + sql.SQL(" AND ").join(clauses)
    cursor = conn.execute(query, values)
    return [item.name for item in cursor.description], cursor.fetchall()


def update_row(conn, name, key_raw, changes):
    key = spec(name)["key"]
    key_value = convert(name, key, key_raw)
    if key_value is None:
        raise ValueError(f"нужно значение {key}")
    assignments = []
    values = []
    for field, raw in changes.items():
        assignments.append(sql.SQL("{} = %s").format(column(name, field, writable=True)))
        values.append(convert(name, field, raw))
    if not assignments:
        raise ValueError("нужна хотя бы одна колонка")
    values.append(key_value)
    query = sql.SQL("UPDATE {} SET {} WHERE {} = %s").format(
        sql.Identifier(name), sql.SQL(", ").join(assignments), sql.Identifier(key)
    )
    touched = conn.execute(query, values).rowcount
    if not touched:
        raise ValueError(f"в таблице {name} нет записи с {key} = {key_value}")
    return touched


def update_rows(conn, name, field, raw, by_field, raws):
    spec(name)
    query = sql.SQL("UPDATE {} SET {} = %s WHERE {} = ANY(%s)").format(
        sql.Identifier(name), column(name, field, writable=True), column(name, by_field)
    )
    values = [convert(name, field, raw), [convert(name, by_field, item) for item in raws]]
    return conn.execute(query, values).rowcount


def insert_query(name, fields, rows):
    key = spec(name)["key"]
    names = [column(name, field, writable=True) for field in fields]
    if not names:
        raise ValueError("нужна хотя бы одна колонка")
    groups = []
    values = []
    for row in rows:
        groups.append(sql.SQL("({})").format(sql.SQL(", ").join([sql.Placeholder()] * len(fields))))
        values.extend(convert(name, field, raw) for field, raw in zip(fields, row))
    query = sql.SQL("INSERT INTO {} ({}) VALUES {} RETURNING {}").format(
        sql.Identifier(name), sql.SQL(", ").join(names), sql.SQL(", ").join(groups), sql.Identifier(key)
    )
    return query, values


def insert_rows(conn, name, fields, rows):
    query, values = insert_query(name, fields, rows)
    return [row[0] for row in conn.execute(query, values).fetchall()]


def insert_tree(conn, name, fields, child, fields_of_child, batch):
    link = spec(name)["children"].get(child)
    if link is None:
        raise ValueError(f"у таблицы {name} нет дочерней таблицы {child}")
    created = []
    with conn.transaction():
        for row, child_rows in batch:
            query, values = insert_query(name, fields, [row])
            parent_id = conn.execute(query, values).fetchone()[0]
            child_ids = []
            if child_rows:
                query, values = insert_query(
                    child, [link] + fields_of_child, [[str(parent_id)] + child_row for child_row in child_rows]
                )
                child_ids = [row[0] for row in conn.execute(query, values).fetchall()]
            created.append((parent_id, child_ids))
    return created

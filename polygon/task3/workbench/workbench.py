import readline
import sys
from getpass import getpass
from pathlib import Path

import psycopg
import yaml

import messages
import storage

PROFILE = Path(__file__).with_name("config.yaml")

MENU = """
1  показать таблицу
2  показать таблицу с фильтром
3  изменить запись по id
4  изменить несколько записей
5  добавить запись
6  добавить запись с дочерними
7  добавить несколько записей
8  добавить несколько записей с дочерними
0  выход"""


def load_profile():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not all(profile.get(key) for key in ("host", "port", "database")):
        raise ValueError(f"в {PROFILE.name} нужны host, port и database")
    return profile


def read_intact(prompt, read):
    while True:
        answer = read(prompt)
        try:
            answer.encode("utf-8")
        except UnicodeEncodeError:
            print("Ввод поврежден или не в UTF-8, повторите", file=sys.stderr)
            continue
        return answer


def ask(prompt):
    return read_intact(prompt, input).strip()


def ask_table(names, prompt="Таблица"):
    while True:
        name = ask(f"{prompt} [{', '.join(names)}]: ")
        if name in names:
            return name
        print("Нет такой таблицы", file=sys.stderr)


def ask_field(options, prompt="Колонка"):
    while True:
        field = ask(f"{prompt} [{', '.join(options)}]: ")
        if field in options:
            return field
        print("Нет такой колонки", file=sys.stderr)


def ask_fields(options, prompt="Колонки через запятую"):
    while True:
        parts = [part.strip() for part in ask(f"{prompt} [{', '.join(options)}]: ").split(",")]
        chosen = list(dict.fromkeys(part for part in parts if part))
        strangers = [field for field in chosen if field not in options]
        if chosen and not strangers:
            return chosen
        print("Нужна хотя бы одна колонка из списка" if not chosen else f"Нет таких колонок: {', '.join(strangers)}", file=sys.stderr)


def ask_count(prompt, lowest=1):
    allowed = {str(number): number for number in range(lowest, 51)}
    while True:
        raw = ask(prompt)
        if raw in allowed:
            return allowed[raw]
        print(f"Нужно число от {lowest} до 50", file=sys.stderr)


def ask_row(fields, indent=""):
    return [ask(f"{indent}{field}: ") for field in fields]


def show(header, rows):
    cells = [["NULL" if value is None else str(value) for value in row] for row in rows]
    widths = [max(len(text) for text in col) for col in zip(header, *cells)]
    print(" | ".join(text.ljust(width) for text, width in zip(header, widths)))
    print("-+-".join("-" * width for width in widths))
    for row in cells:
        print(" | ".join(text.ljust(width) for text, width in zip(row, widths)))


def view(conn, filtered):
    name = ask_table(list(storage.SCHEMA))
    filters = []
    while filtered:
        field = ask_field(list(storage.SCHEMA[name]["fields"]))
        filters.append((field, ask(f"{field} = ")))
        if ask("Еще условие? [y/N]: ").lower() != "y":
            break
    header, rows = storage.select_rows(conn, name, filters)
    show(header, rows)
    return f"{name}, строк: {len(rows)}"


def change_one(conn):
    name = ask_table(list(storage.SCHEMA))
    key_raw = ask(f"{storage.SCHEMA[name]['key']} записи: ")
    fields = ask_fields(storage.editable(name))
    changes = {field: ask(f"{field} (пусто = NULL): ") for field in fields}
    touched = storage.update_row(conn, name, key_raw, changes)
    return f"{name}, обновлено строк: {touched}"


def change_many(conn):
    name = ask_table(list(storage.SCHEMA))
    field = ask_field(storage.editable(name), "Колонка для изменения")
    raw = ask(f"Новое значение {field} (пусто = NULL): ")
    by_field = ask_field(list(storage.SCHEMA[name]["fields"]), "Колонка для условия IN")
    raws = [part.strip() for part in ask(f"Значения {by_field} через запятую: ").split(",") if part.strip()]
    if not raws:
        raise ValueError("нужно хотя бы одно значение для IN")
    touched = storage.update_rows(conn, name, field, raw, by_field, raws)
    return f"{name}, обновлено строк: {touched}"


def add_rows(conn, many):
    name = ask_table(list(storage.SCHEMA))
    fields = ask_fields(storage.editable(name))
    count = ask_count("Сколько записей: ") if many else 1
    rows = []
    for number in range(1, count + 1):
        if many:
            print(f"Запись {number}")
        rows.append(ask_row(fields))
    ids = storage.insert_rows(conn, name, fields, rows)
    return f"{name}, добавлены id: {', '.join(map(str, ids))}"


def add_tree(conn, many):
    parents = [name for name in storage.SCHEMA if storage.SCHEMA[name]["children"]]
    name = ask_table(parents, "Родительская таблица")
    fields = ask_fields(storage.editable(name))
    child = ask_table(list(storage.SCHEMA[name]["children"]), "Дочерняя таблица")
    fields_of_child = ask_fields(storage.child_fields(name, child), f"Колонки {child} через запятую")
    count = ask_count("Сколько записей: ") if many else 1
    batch = []
    for number in range(1, count + 1):
        if many:
            print(f"Запись {number}")
        row = ask_row(fields)
        child_rows = []
        for child_number in range(1, ask_count(f"Сколько записей {child}: ", lowest=0) + 1):
            print(f"  {child} {child_number}")
            child_rows.append(ask_row(fields_of_child, "  "))
        batch.append((row, child_rows))
    created = storage.insert_tree(conn, name, fields, child, fields_of_child, batch)
    return "; ".join(f"{name} {parent_id} с {child} {', '.join(map(str, child_ids)) or '-'}" for parent_id, child_ids in created)


ACTIONS = {
    "1": ("Выборка", lambda conn: view(conn, False)),
    "2": ("Выборка", lambda conn: view(conn, True)),
    "3": ("Правка", change_one),
    "4": ("Правка", change_many),
    "5": ("Вставка", lambda conn: add_rows(conn, False)),
    "6": ("Вставка", lambda conn: add_tree(conn, False)),
    "7": ("Вставка", lambda conn: add_rows(conn, True)),
    "8": ("Вставка", lambda conn: add_tree(conn, True)),
}


def connect(profile, journal):
    login = ask("Логин: ")
    secret = read_intact("Пароль: ", getpass)
    try:
        conn = psycopg.connect(
            host=profile["host"],
            port=profile["port"],
            dbname=profile["database"],
            user=login,
            password=secret,
            connect_timeout=5,
            options="-c statement_timeout=5000",
            autocommit=True,
        )
    except psycopg.Error as error:
        messages.failure(journal, "Подключение не удалось", error, "нет связи с базой данных или неверны логин и пароль")
        sys.exit(1)
    journal.info("Подключение к %s:%s/%s как %s выполнено", profile["host"], profile["port"], profile["database"], login)
    return conn


def serve(conn, journal):
    while True:
        print(MENU)
        choice = ask("> ")
        if choice == "0":
            return
        if choice not in ACTIONS:
            print("Нет такого пункта", file=sys.stderr)
            continue
        label, action = ACTIONS[choice]
        try:
            outcome = action(conn)
        except ValueError as error:
            journal.error("%s не выполнена: %s", label, error)
            continue
        except psycopg.Error as error:
            messages.failure(journal, f"{label} не выполнена", error)
            continue
        journal.info("%s выполнена: %s", label, outcome)


def main():
    journal = messages.open_journal()
    try:
        profile = load_profile()
    except ValueError as error:
        journal.error("Конфиг: %s", error)
        sys.exit(1)
    except (OSError, yaml.YAMLError) as error:
        journal.error("Конфиг %s не прочитан", PROFILE.name, extra={"detail": f" | {error}"})
        sys.exit(1)

    with connect(profile, journal) as conn:
        serve(conn, journal)


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\nВыход")

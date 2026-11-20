from pathlib import Path
from secrets import token_hex, token_urlsafe
from threading import Lock
from time import monotonic

import psycopg
import yaml
from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for

import messages
import storage

PROFILE = Path(__file__).with_name("config.yaml")
SESSION_SECONDS = 30 * 60
BATCH_LIMIT = 50


def load_profile():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    if not isinstance(profile, dict) or not all(profile.get(key) for key in ("host", "port", "database")):
        raise ValueError(f"в {PROFILE.name} нужны host, port и database")
    return profile


app = Flask(__name__)
app.config.update(SECRET_KEY=token_hex(32), SESSION_COOKIE_NAME="workbench_session",
                  SESSION_COOKIE_SAMESITE="Strict", MAX_CONTENT_LENGTH=8 * 1024 * 1024)
profile = load_profile()
journal = messages.open_journal()
sessions = {}
sessions_lock = Lock()


def connect(login, password):
    return psycopg.connect(
        host=profile["host"], port=profile["port"], dbname=profile["database"],
        user=login, password=password, connect_timeout=5, options="-c statement_timeout=5000",
    )


@app.before_request
def check_session():
    now = monotonic()
    with sessions_lock:
        for token, state in list(sessions.items()):
            if state["expires"] <= now:
                del sessions[token]
        g.state = sessions.get(session.get("sid"), {})
        g.account = g.state.get("account")
    if not g.account and request.endpoint not in ("login", None):
        return redirect(url_for("login"))
    if request.method == "POST":
        if not session.get("csrf") or request.form.get("csrf") != session["csrf"]:
            abort(400, "Обновите страницу и отправьте форму еще раз.")


def clear_session():
    with sessions_lock:
        sessions.pop(session.get("sid"), None)
    session.clear()


@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if g.account:
            return redirect(url_for("home"))
        if "csrf" not in session:
            session["csrf"] = token_urlsafe(32)
        return render_template("login.html")

    username = request.form.get("login", "").strip()
    password = request.form.get("password", "")
    try:
        if not username or not password or "\0" in username or "\0" in password:
            raise ValueError
        with connect(username, password):
            pass
    except (psycopg.Error, ValueError):
        journal.error("Неудачная попытка входа: логин=%r, адрес=%s", username[:100], request.remote_addr)
        return render_template("login.html", error="Не удалось войти. Проверьте логин и пароль и доступность БД."), 401

    clear_session()
    token = token_urlsafe(32)
    with sessions_lock:
        sessions[token] = {"account": (username, password), "expires": monotonic() + SESSION_SECONDS}
    session.update(sid=token, csrf=token_urlsafe(32))
    journal.info("Подключение к %s выполнено: логин=%r", profile["database"], username)
    return redirect(url_for("home"))


@app.post("/logout")
def logout():
    clear_session()
    return redirect(url_for("login"))


@app.get("/home")
def home():
    return render_template("home.html")


def current_table(available=storage.SCHEMA):
    name = request.args.get("table", "sectors")
    if name not in available:
        abort(404)
    return name


def current_mode(*allowed):
    mode = request.args.get("mode", allowed[0])
    if mode not in allowed:
        abort(404)
    return mode


def failed(action, name, error):
    text = messages.explain(error)
    journal.error("%s не выполнена: %s, %s", action, name, text)
    return text


def selected_fields(table, key="field", skip=None):
    fields = list(dict.fromkeys(request.form.getlist(key)))
    allowed = storage.editable(table)
    if not fields or any(f not in allowed or f == skip for f in fields):
        raise ValueError(f"выберите колонки из списка {table}")
    return fields


def form_row(prefix, fields):
    row = []
    for field in fields:
        key = f"{prefix}.{field}"
        if key not in request.form:
            raise ValueError(f"в форме отсутствует поле {field}")
        row.append(request.form[key].strip())
    return row


def row_count(raw, lowest):
    try:
        count = int(raw)
    except ValueError:
        raise ValueError("количество строк должно быть целым числом") from None
    if not lowest <= count <= BATCH_LIMIT:
        raise ValueError(f"количество строк должно быть от {lowest} до {BATCH_LIMIT}")
    return count


@app.get("/view")
def view():
    name = current_table()
    fields = request.args.getlist("field")
    filtered = current_mode("all", "filter") == "filter" or bool(fields)
    filters = []
    try:
        ops = request.args.getlist("op") or ["eq"] * len(fields)
        values = request.args.getlist("value")
        if len(fields) != len(ops) or len(fields) != len(values):
            raise ValueError("для каждого условия нужны колонка и значение")
        filters = [(f, op, raw.strip()) for f, op, raw in zip(fields, ops, values) if f]
        if filtered and ("more" in request.args or not fields):
            return render_template("view.html", name=name, filtered=True, filters=filters)
        with connect(*g.account) as conn:
            header, rows = storage.select_rows(conn, name, filters)
    except (ValueError, psycopg.Error) as error:
        return render_template("view.html", name=name, filtered=filtered, filters=filters,
                               error=failed("Выборка", name, error)), 400
    journal.info("Выборка выполнена: %s, строк: %d", name, len(rows))
    return render_template("view.html", name=name, filtered=filtered, filters=filters, fields=header, rows=rows)


def insert_fields(name, key="field", link=None):
    fields = selected_fields(name, key, link)
    missing = [f for f in storage.REQUIRED[name] if f != link and f not in fields]
    if missing:
        raise ValueError(f"{name}: обязательные колонки: {', '.join(missing)}")
    return fields


def add_rows(page, action):
    name, fields = page["name"], page["fields"]
    page["step"] = "values"
    if action == "prepare":
        return render_template("add.html", **page)
    if action != "save":
        raise ValueError("неизвестное действие формы")
    rows = [form_row(f"p.{i}", fields) for i in range(page["count"])]
    with connect(*g.account) as conn:
        ids = storage.insert_rows(conn, name, fields, rows)
    return receipt(name, page["mode"], f"{name}, добавлены id: {', '.join(map(str, ids))}")


def add_tree(page, action):
    name, fields, count = page["name"], page["fields"], page["count"]
    child, link = storage.CHILDREN[name]
    page.update(step="counts", child=child, link=link, counts=[0] * count)
    if action == "prepare":
        return render_template("add.html", **page)
    raw_counts = request.form.getlist("children")
    if len(raw_counts) != count:
        raise ValueError("укажите количество дочерних строк для каждого родителя")
    counts = [row_count(raw, 0) for raw in raw_counts]
    page.update(counts=counts, child_fields=[])
    if any(counts):
        page["step"] = "columns"
        if action == "children":
            return render_template("add.html", **page)
        page["child_fields"] = insert_fields(child, "child_field", link)
    page["step"] = "values"
    if action in ("children", "rows"):
        return render_template("add.html", **page)
    if action != "save":
        raise ValueError("неизвестное действие формы")
    child_fields = page["child_fields"]
    batch = [(form_row(f"p.{i}", fields), [form_row(f"c.{i}.{j}", child_fields) for j in range(n)])
             for i, n in enumerate(counts)]
    with connect(*g.account) as conn:
        created = storage.insert_tree(conn, name, fields, child_fields, batch)
    outcome = "; ".join(f"{name} {key}: {child} {', '.join(map(str, ids)) or 'нет'}" for key, ids in created)
    return receipt(name, page["mode"], outcome)


@app.route("/add", methods=["GET", "POST"])
def add():
    mode = current_mode("one", "many", "tree", "trees")
    tree = mode in ("tree", "trees")
    available = storage.CHILDREN if tree else storage.SCHEMA
    name = current_table(available)
    page = dict(name=name, mode=mode, available=available, fields=storage.REQUIRED[name], count=1, step="setup")
    if request.method == "GET":
        return render_template("add.html", **page)
    try:
        page["fields"] = insert_fields(name)
        page["count"] = row_count(request.form.get("count", "1"), 1)
        if mode in ("one", "tree") and page["count"] != 1:
            raise ValueError("этот режим добавляет одну запись")
        action = request.form.get("action")
        return add_tree(page, action) if tree else add_rows(page, action)
    except (ValueError, psycopg.Error) as error:
        return render_template("add.html", **page, error=failed("Вставка", name, error)), 400


def receipt(name, mode, outcome):
    journal.info("Вставка выполнена: %s", outcome)
    token = token_urlsafe(16)
    with sessions_lock:
        receipts = g.state.setdefault("receipts", {})
        receipts[token] = (name, mode, outcome)
        if len(receipts) > 10:
            del receipts[next(iter(receipts))]
    return redirect(url_for("inserted", result=token), code=303)


@app.get("/added/<result>")
def inserted(result):
    with sessions_lock:
        saved = g.state.get("receipts", {}).get(result)
    if saved is None:
        return redirect(url_for("home"))
    name, mode, outcome = saved
    return render_template("add.html", mode=mode, outcome=outcome, saved_table=name)


@app.route("/update", methods=["GET", "POST"])
def update():
    mode = current_mode("many", "one")
    name = current_table()
    if request.method == "POST":
        form = request.form
        try:
            with connect(*g.account) as conn:
                if mode == "one":
                    fields = selected_fields(name)
                    changes = dict(zip(fields, form_row("set", fields)))
                    touched = storage.update_row(conn, name, form.get("id", ""), changes)
                else:
                    raw = form.get("values", "")
                    parts = raw.split(",") if form.get("separator") == "comma" else raw.splitlines()
                    raws = [part.strip() for part in parts if part.strip()]
                    touched = storage.update_rows(conn, name, form.get("field", ""), form.get("value", "").strip(),
                                                 form.get("by_field", ""), raws)
        except (ValueError, psycopg.Error) as error:
            return render_template("update.html", name=name, mode=mode, error=failed("Правка", name, error)), 400
        journal.info("Правка выполнена: %s, обновлено строк: %d", name, touched)
        flash(f"{name}: обновлено строк: {touched}")
        return redirect(url_for("view", table=name), code=303)
    return render_template("update.html", name=name, mode=mode)


app.jinja_env.globals.update(tables=storage.SCHEMA, required=storage.REQUIRED, options=storage.OPTIONS, hints=storage.HINTS)

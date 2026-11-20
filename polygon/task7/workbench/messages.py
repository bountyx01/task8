import logging
import os
import sys

import psycopg
from psycopg import errors

ENTRY = "%(levelname)s %(asctime)s %(message)s"
STAMP = "%d.%m.%Y %H:%M:%S"

EXPLANATIONS = (
    (errors.UniqueViolation, "такая запись уже существует"),
    (errors.ForeignKeyViolation, "ссылка на несуществующую запись в связанной таблице"),
    (errors.NotNullViolation, "не заполнено обязательное поле"),
    (errors.CheckViolation, "значение не проходит проверку ограничения таблицы"),
    (errors.InsufficientPrivilege, "недостаточно прав для этой операции"),
    (errors.QueryCanceled, "запрос отменен по тайм-ауту"),
    (psycopg.DataError, "неверный формат или диапазон значения"),
    (psycopg.OperationalError, "нет связи с базой данных"),
)


def open_journal():
    journal = logging.getLogger("workbench")
    journal.setLevel(logging.INFO)
    journal.propagate = False
    brief = logging.Formatter(ENTRY, datefmt=STAMP)
    console = logging.StreamHandler(sys.stdout)
    console.addFilter(lambda record: record.levelno < logging.ERROR)
    errors_only = logging.StreamHandler(sys.stderr)
    errors_only.setLevel(logging.ERROR)
    for handler in (console, errors_only):
        handler.setFormatter(brief)
        journal.addHandler(handler)
    path = os.environ.get("WORKBENCH_LOG")
    if path:
        try:
            trace = logging.FileHandler(path, encoding="utf-8")
        except OSError:
            journal.error("Файл логов %s недоступен, пишу только в консоль", path)
        else:
            trace.setFormatter(brief)
            journal.addHandler(trace)
    return journal


def explain(error):
    if isinstance(error, ValueError):
        return str(error)
    for kind, text in EXPLANATIONS:
        if isinstance(error, kind):
            return text
    return "запрос не выполнен"

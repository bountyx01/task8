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


def below_error(record):
    return record.levelno < logging.ERROR


def open_journal():
    journal = logging.getLogger("workbench")
    journal.setLevel(logging.INFO)
    journal.propagate = False

    brief = logging.Formatter(ENTRY, datefmt=STAMP)

    regular = logging.StreamHandler(sys.stdout)
    regular.setFormatter(brief)
    regular.addFilter(below_error)
    journal.addHandler(regular)

    alarming = logging.StreamHandler(sys.stderr)
    alarming.setLevel(logging.ERROR)
    alarming.setFormatter(brief)
    journal.addHandler(alarming)

    trace_path = os.environ.get("WORKBENCH_LOG")
    if trace_path:
        try:
            os.makedirs(os.path.dirname(trace_path) or ".", exist_ok=True)
            trace = logging.FileHandler(trace_path, encoding="utf-8")
        except OSError:
            journal.error("Файл логов %s недоступен, пишу только в консоль", trace_path)
        else:
            trace.setFormatter(logging.Formatter(ENTRY + "%(detail)s", datefmt=STAMP, defaults={"detail": ""}))
            journal.addHandler(trace)

    return journal


def explain(error):
    for kind, text in EXPLANATIONS:
        if isinstance(error, kind):
            return text
    return "запрос не выполнен"


def failure(journal, text, error, explanation=None):
    code = getattr(error, "sqlstate", None) or "-"
    journal.error("%s: %s", text, explanation or explain(error), extra={"detail": f" | {code} {error}"})

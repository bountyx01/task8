# Восьмая работа по предмету

Цель: проверить cli приложение задания 3 и web приложение задания 7. Semgrep выбран 1.186.0 (ищет проблемы в .py, .sh, Dockerfile, compose.yaml), Bandit выбран 1.9.4 (ищет проблемы в .py)

## Целевые исходники

Располагаются в `polygon/` (`task3` и `task7`). Являются копиями ранних репозиториев, однако (для наличия замечаний) туда добавлен файл `feat_merge_please.py`, в котором есть несколько не хороших функциональностей, которые целевые инструменты должны были найти.

Запустить сканирования можно как:
```bash
./scripts/scan.sh polygon/task3 reports/task3
./scripts/scan.sh polygon/task7 reports/task7
```

Далее необходимо создать triage.json с результатами ручной валидации результатов.

Для удобства - команда, чтобы скопировать "скелет" scan.json в triage.json:
```bash
for task8_app in task3 task7; do
  jq '[.findings[] | {ids: [.id], type: .rule, reason: "", priority: ""}]' \
    "reports/$task8_app/scan.json" > "reports/$task8_app/triage.json"
done
```

Затем необходимо собрать отчет
```bash
python3 -I scripts/make_report.py reports/task3 reports/task7 -o reports/report.md
```

Отчет доступен в `reports/report.md`

#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
if [ -e .env ]; then
  echo ".env уже существует" >&2
  exit 1
fi
umask 077
postgres_password=$(openssl rand -hex 24)
judge_password=$(openssl rand -hex 24)
filled=$(sed -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$postgres_password|" \
  -e "s|^JUDGE_PASSWORD=.*|JUDGE_PASSWORD=$judge_password|" \
  -e "s|^LOCAL_UID=.*|LOCAL_UID=$(id -u)|" \
  -e "s|^LOCAL_GID=.*|LOCAL_GID=$(id -g)|" .env.example)
printf '%s\n' "$filled" >.env
echo "Создан .env"

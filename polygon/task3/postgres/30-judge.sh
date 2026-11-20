#!/bin/bash
set -e
psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -v judge="$JUDGE_USER" -v judge_password="$JUDGE_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
REVOKE CONNECT ON DATABASE postgres, template1 FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
CREATE ROLE :"judge" LOGIN PASSWORD :'judge_password';
GRANT CONNECT ON DATABASE :"db" TO :"judge";
GRANT USAGE ON SCHEMA public TO :"judge";
GRANT SELECT ON ALL TABLES IN SCHEMA public TO :"judge";
GRANT INSERT (name, industry, description), UPDATE (name, industry, description) ON sectors TO :"judge";
GRANT INSERT (sector_id, hostname, ip, os, is_critical), UPDATE (sector_id, hostname, ip, os, is_critical) ON hosts TO :"judge";
GRANT INSERT (name, country, members, score), UPDATE (name, country, members, score) ON teams TO :"judge";
GRANT INSERT (team_id, host_id, event, severity, status, points, submitted_at),
      UPDATE (team_id, host_id, event, severity, status, points, submitted_at) ON reports TO :"judge";
SQL

FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends python3-venv ca-certificates curl && rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/scan && /opt/scan/bin/pip install --no-cache-dir semgrep==1.186.0
ARG RULES_REV=a5ad1714f00c9f7fde980cab0ea1d6dc6d414fd2
ARG RULES_SHA=e5a7ec33035fc7707b87385cb99e1228c76b1604efe5439e92891f3005714cc3
RUN set -eu; mkdir /tmp/download /tmp/unpack /opt/rules; curl -fsSL "https://codeload.github.com/semgrep/semgrep-rules/tar.gz/$RULES_REV" -o /tmp/download/rules.tgz; printf '%s  %s\n' "$RULES_SHA" /tmp/download/rules.tgz | sha256sum -c -; tar -xzf /tmp/download/rules.tgz -C /tmp/unpack; cd "/tmp/unpack/semgrep-rules-$RULES_REV"; find python/lang/security bash/lang/security bash/curl/security dockerfile/security yaml/docker-compose/security -type f \( -name '*.yaml' -o -name '*.yml' \) ! -name '*.test.yaml' ! -name '*.test.yml' -exec cp --parents '{}' /opt/rules/ \;; rm -rf /tmp/download /tmp/unpack
LABEL scan.version="1.186.0" scan.rules="$RULES_REV" scan.rules.sha256="$RULES_SHA"
ENV PATH=/opt/scan/bin:$PATH HOME=/tmp XDG_CACHE_HOME=/tmp/cache PYTHONDONTWRITEBYTECODE=1
WORKDIR /src
ENTRYPOINT ["semgrep", "scan", "--config=/opt/rules", "--metrics=off", "--disable-version-check", "--strict", "--jobs=2", "--json-output=/out/semgrep.json"]
CMD ["."]

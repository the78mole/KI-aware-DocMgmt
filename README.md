# KI-aware-DocMgmt

[![Renovate](https://img.shields.io/badge/renovate-enabled-brightgreen.svg)](https://renovatebot.com)

KI-gestütztes Dokumentenmanagement.

## OpenBao

Credentials kommen aus OpenBao, Namespace `it-infra` (KV v2 unter `secret/`).
direnv lädt beim Betreten des Verzeichnisses die `.env` (gitignored, mode 600) mit
einem scoped, nur lesenden Token und ersetzt damit den `~/GIT`-Sperr-Riegel.

```bash
cp .env.example .env && chmod 600 .env   # Token eintragen
direnv allow
bao kv list secret/
```

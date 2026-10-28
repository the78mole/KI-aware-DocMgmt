# KI-aware-DocMgmt

[![Backend Tests](https://github.com/the78mole/KI-aware-DocMgmt/actions/workflows/backend-tests.yml/badge.svg)](https://github.com/the78mole/KI-aware-DocMgmt/actions/workflows/backend-tests.yml)
[![Frontend Tests](https://github.com/the78mole/KI-aware-DocMgmt/actions/workflows/frontend-tests.yml/badge.svg)](https://github.com/the78mole/KI-aware-DocMgmt/actions/workflows/frontend-tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Renovate](https://img.shields.io/badge/renovate-enabled-brightgreen.svg)](https://renovatebot.com)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

KI-gestütztes Dokumentenmanagement.

## Aufbau

| Verzeichnis | Inhalt | Stack |
|---|---|---|
| [`backend/`](backend/) | API | Python, FastAPI, uv, ruff, pytest |
| [`frontend/`](frontend/) | Web-UI | React, TypeScript, Vite, Vitest, oxlint, Prettier |

## Entwicklung

```bash
(cd backend && uv sync && uv run fastapi dev src/docmgmt/main.py)   # :8000
(cd frontend && npm install && npm run dev)                          # :5173, /api -> :8000
pre-commit install
```

## OpenBao

Credentials kommen aus OpenBao, Namespace `it-infra` (KV v2 unter `secret/`).
direnv lädt beim Betreten des Verzeichnisses die `.env` (gitignored, mode 600) mit
einem scoped, nur lesenden Token und ersetzt damit den `~/GIT`-Sperr-Riegel.

```bash
cp .env.example .env && chmod 600 .env   # Token eintragen
direnv allow
bao kv list secret/
```

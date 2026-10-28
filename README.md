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

## Compose-Stack

Startet DocMgmt (API + SPA auf `:8000`), den Konvertierungs-Worker, marker-pdf (nur CPU), PostgreSQL und
Garage als S3-Speicher. marker lädt beim ersten Start seine Modelle (mehrere GB) ins Volume `marker-models`.
`scripts/dev-secrets.sh` ergänzt die `.env` um zufällige Secrets, vorhandene Werte bleiben erhalten.

```bash
./scripts/dev-secrets.sh
docker compose up -d --build
curl -F file=@datenblatt.pdf -F title="LM317" localhost:8000/api/documents
```

`garage-init` legt beim Start Layout, Bucket und Zugangsschlüssel per Admin-API an und ist idempotent.
Um später auf externe Dienste umzuziehen, genügen die `S3_*`-Variablen bzw. `MARKER_URL`.

Jedes eingecheckte PDF bekommt eine Konvertierung im Status `pending`. Der Worker holt sie aus Postgres
(`FOR UPDATE SKIP LOCKED`), schickt das PDF an marker und speichert Markdown und Metadaten (`jsonb`) in der
Tabelle `conversions`, die Bilder in S3 unter `documents/{id}/conversions/{conversion_id}/`. Jeder Lauf bleibt
erhalten, ausgeliefert wird der neueste erfolgreiche. Das Schema verwaltet Alembic, die API migriert beim Start.

| Endpunkt | Zweck |
|---|---|
| `POST /api/documents` | PDF einchecken (multipart: `file`, optional `title`), Duplikate per SHA-256 → `409` |
| `GET /api/documents` | Liste, neueste zuerst |
| `GET /api/documents/{id}` | Metadaten |
| `GET /api/documents/{id}/file` | Original-PDF |
| `GET /api/documents/{id}/markdown` | Markdown der neuesten erfolgreichen Konvertierung (Header `X-Conversion-Id`) |
| `GET /api/documents/{id}/conversions` | Alle Konvertierungsläufe mit Status, Fehler, Bildliste |
| `POST /api/documents/{id}/conversions` | Neue Konvertierung anstoßen (`409`, solange eine läuft) |
| `GET /api/documents/{id}/conversions/{cid}/assets/{name}` | Bild aus dem Markdown |

## OpenBao

Credentials kommen aus OpenBao, Namespace `it-infra` (KV v2 unter `secret/`).
direnv lädt beim Betreten des Verzeichnisses die `.env` (gitignored, mode 600) mit
einem scoped, nur lesenden Token und ersetzt damit den `~/GIT`-Sperr-Riegel.

```bash
cp .env.example .env && chmod 600 .env   # Token eintragen
direnv allow
bao kv list secret/
```

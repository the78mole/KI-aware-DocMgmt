# CLAUDE.md — KI-aware-DocMgmt

Übergabe- und Arbeitsdokument für Claude. Stand: 2026-10-28 (Initial-Setup abgeschlossen).

## Projekt

KI-gestütztes Dokumentenmanagement. Öffentliches Repo: https://github.com/the78mole/KI-aware-DocMgmt
(Branch `main`). Die fachlichen Anforderungen sind **noch nicht festgelegt** — vor größeren
Architekturentscheidungen (Speicher, Datenbank, KI-Anbieter, OCR, Auth) mit Daniel klären.

## Aufbau

| Verzeichnis | Inhalt | Stack |
|---|---|---|
| `backend/` | API, Paket `ki-docmgmt`, Import `docmgmt` (src-Layout) | Python ≥3.12, FastAPI, uv, hatchling, ruff, pytest + pytest-cov |
| `frontend/` | Web-UI, Paket `ki-docmgmt-frontend` | React 19, TypeScript, Vite, Vitest + coverage-v8, oxlint, Prettier, npm |

Ziel: Datenblätter (PDF) einchecken, in S3 ablegen, per marker-pdf in Markdown wandeln und verknüpfen;
Zugriff über UI, REST-API und HTTP-MCP.

Bisher implementiert: `GET /api/health`, Check-in `POST/GET /api/documents[/{id}[/file]]` (Postgres-Metadaten,
PDF in S3 unter `documents/{id}/original.pdf`, Dedup per SHA-256) und `compose.yaml` mit DocMgmt, Postgres und
Garage. Das Backend-Image liefert die gebaute SPA mit aus (`STATIC_DIR`). Der Vite-Dev-Server leitet `/api` auf
`http://127.0.0.1:8000` weiter.

Konvertierung: Tabelle `conversions` (1:n zum Dokument, jeder marker-Lauf bleibt erhalten). Markdown (`text`) und
marker-Metadaten (`jsonb`) liegen in Postgres, Bilder in S3 unter `documents/{id}/conversions/{cid}/`.
`docmgmt.worker` nutzt Postgres als Queue und spricht `marker_server` (`POST /marker/upload`) über
`MarkerServerConverter`; ein weiterer Converter für holy-moly-mcp kann dasselbe Protokoll implementieren.
Schema per Alembic (`src/docmgmt/migrations`, Konfiguration in `pyproject.toml`), die API migriert beim Start.
Neue Migration: `DATABASE_URL=sqlite:////tmp/x.db uv run alembic upgrade head && … alembic revision --autogenerate`.

Infrastruktur: zunächst alles im Compose-Stack, später extern (Garage-VM als S3, marker über den Dienst
holy-moly-mcp). Der Server hat nur CPU. Garage bindet an `0.0.0.0`, weil nicht jeder Host IPv6 hat.

```bash
(cd backend && uv sync && uv run fastapi dev src/docmgmt/main.py)   # :8000, Docs unter /docs
(cd frontend && npm install && npm run dev)                          # :5173
(cd backend && uv run pytest --cov)
(cd frontend && npm run test -- --coverage && npm run lint && npm run format:check)
pre-commit run --all-files
```

## Konventionen (Daniels Standards)

- **Python:** uv only (`uv add`, `uv run`), ruff für Lint und Format (kein black/isort),
  `line-length = 120`. Tests unter `backend/tests/`, I/O lieber über Fakes als über Mocks testen.
- **Frontend:** npm, Prettier (`semi: false`, `singleQuote`, `printWidth: 100`). Das Vite-Template
  bringt oxlint statt ESLint mit, das wurde bewusst so übernommen.
- **Coverage:** mindestens 80 % auf neuem Code. Das Backend-CI erzwingt `--cov-fail-under=80`.
- **pre-commit** ist installiert: Basis-Hooks, check-jsonschema, ruff (nur `backend/`),
  oxlint/Prettier als lokale Hooks (setzen `npm install` in `frontend/` voraus). `tsconfig*.json`
  sind JSONC und von `check-json` ausgenommen. Vor jedem Commit muss der Lauf grün sein.
- **CI:** `.github/workflows/backend-tests.yml` und `frontend-tests.yml`, jeweils nur bei
  Änderungen im eigenen Verzeichnis (path-gefiltert). `marker-image.yml` baut `deploy/marker/` und pusht
  auf `main` nach GHCR (`ki-aware-docmgmt-marker`), auf PRs wird nur gebaut. Die marker-Version steht als
  `ARG MARKER_VERSION` im Dockerfile und wird zum Image-Tag. Action-Versionen vor jeder Änderung prüfen
  (`gh api repos/<owner>/<repo>/releases/latest`). Floating Major nehmen, wo es eines gibt
  (`actions/checkout@v7`, `actions/setup-node@v7`), `astral-sh/setup-uv` exakt pinnen (`v10.3.2`).
- **Renovate:** `renovate.json` ist Daniels feste Baseline, nicht verändern.
- **Commits:** Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:` …). Commit und Push nur,
  wenn Daniel darum bittet.
- `.github/FUNDING.yml` bleibt wie es ist (Pflicht in allen Repos).

## OpenBao (Secrets)

- Server `https://openbao.intern.chaintronics.com/`, Namespace **`it-infra`**, KV v2 unter `secret/`.
- `.envrc` und `.env` (mode 600, gitignored) setzen ein **scoped, nur lesendes** Token
  (`token-ki-aware-docmgmt`, Policies `default` + `it-infra-read`, verifiziert 2026-10-28).
  Schreiben ist absichtlich nicht möglich. Wenn ein Secret geschrieben werden muss, Daniel fragen.
- **Wichtig für Claude Desktop:** direnv greift nur in interaktiven Shells. Deshalb jeden `bao`-Aufruf
  als `direnv exec . bao …` aus dem Repo-Root ausführen. Ohne das gilt der `~/GIT`-Riegel
  (`BAO_TOKEN=disabled-…`), und es kommt `403` zurück. Das ist gewollt und kein Fehler.
- **Niemals** `unset BAO_TOKEN` oder `env -u BAO_TOKEN` verwenden, denn dann fällt `bao` auf das
  Root-Token in `~/.vault-token` zurück. `~/.vault-token` und `.env` nie ausgeben.
- Secret-Werte nie ausgeben. Nur zuweisen (`X=$(bao kv get -field=… secret/…)`) oder die Struktur
  ansehen: `bao kv get -format=json secret/<name> | jq '.data.data|keys'`.
- Ein Eintrag ist ein KeePass-artiger Datensatz: `url` plus `username`/`password` oder
  `token`/`api_key`, dazu `notes`. Feldnamen in `snake_case`.
- Die App selbst soll Credentials zur Laufzeit aus OpenBao beziehen. Keine Secrets in Code,
  Config-Dateien, Container-Images oder CI-Variablen ohne Rücksprache.

## Offene Punkte / nächste Schritte

1. **marker mit echten Datenblättern auf debian-test prüfen** (marker 2.0 auf CPU im Modus `fast`), danach
   UI (Upload, Liste, PDF/Markdown nebeneinander) und HTTP-MCP.
2. **Anforderungen klären:** Welche Dokumente kommen woher, was soll die KI tun (Klassifikation,
   Extraktion, Suche/RAG, Tagging), wer nutzt die App, und wie wird authentifiziert
   (Keycloak liegt in `it-infra`, es gibt `keycloak` und `bookstack-oidc` als Vorbild für OIDC)?
3. **Release/Deployment festlegen:** z. B. Container-Image auf ghcr.io (Backend liefert die SPA mit
   aus) oder SPA über GitHub Pages. Danach den Release-Workflow mit `paulhatch/semantic-version`
   aufsetzen, mit getrennten Tag-Präfixen `backend/v` und `frontend/v`. Mit Daniel klären, ob
   `bump_each_commit` gewünscht ist, also jeder Commit auf `main` ein Release erzeugt.
   OIDC-Publish-Schritte nicht in Reusable Workflows auslagern. Deployment-Environments
   **vor** dem ersten Lauf per `gh api -X PUT repos/the78mole/KI-aware-DocMgmt/environments/<name>`
   anlegen.
4. **OpenAPI → TS-Client:** Den Frontend-Client aus dem FastAPI-Schema generieren, statt Typen
   von Hand zu pflegen.
5. **Renovate** muss Daniel selbst für das Repo aktivieren (GitHub App), falls das noch nicht geschehen ist.

#!/usr/bin/env bash
# Ergänzt .env um zufällige Secrets für den lokalen Compose-Stack. Vorhandene Werte bleiben.
set -euo pipefail
cd "$(dirname "$0")/.."
touch .env && chmod 600 .env

add() {
  grep -q "^$1=" .env || echo "$1=$2" >> .env
}

add POSTGRES_PASSWORD "$(openssl rand -hex 24)"
add GARAGE_RPC_SECRET "$(openssl rand -hex 32)"
add GARAGE_ADMIN_TOKEN "$(openssl rand -hex 32)"
add S3_ACCESS_KEY_ID "GK$(openssl rand -hex 12)"
add S3_SECRET_ACCESS_KEY "$(openssl rand -hex 32)"
echo "Secrets für den Compose-Stack stehen in .env"

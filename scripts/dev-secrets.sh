#!/usr/bin/env bash
# Ergänzt .env um zufällige Secrets für den lokalen Compose-Stack. Vorhandene Werte bleiben.
set -euo pipefail
cd "$(dirname "$0")/.."
touch .env && chmod 600 .env

add() {
  if grep -q "^$1=." .env; then
    return
  elif grep -q "^$1=$" .env; then
    sed -i "s|^$1=$|$1=$2|" .env   # leere Zeile aus .env.example füllen
  else
    echo "$1=$2" >> .env
  fi
}

add POSTGRES_PASSWORD "$(openssl rand -hex 24)"
add GARAGE_RPC_SECRET "$(openssl rand -hex 32)"
add GARAGE_ADMIN_TOKEN "$(openssl rand -hex 32)"
add S3_ACCESS_KEY_ID "GK$(openssl rand -hex 12)"
add S3_SECRET_ACCESS_KEY "$(openssl rand -hex 32)"
echo "Secrets für den Compose-Stack stehen in .env"

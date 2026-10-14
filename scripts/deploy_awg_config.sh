#!/bin/bash

set -e

SRC="amneziawg/server_config/awg0.conf"
DST="/etc/amnezia/amneziawg/awg0.conf"
TMP_CONFIG="$(mktemp)"

trap 'rm -f "$TMP_CONFIG"' EXIT

echo "Deploying AmneziaWG config"

sudo cp "$SRC" "$DST"
sudo chmod 600 "$DST"

sudo awg-quick strip "$DST" > "$TMP_CONFIG"
sudo awg syncconf awg0 "$TMP_CONFIG"

echo "AmneziaWG config deployed"

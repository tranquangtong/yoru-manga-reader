#!/bin/bash
set -u
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "KHÔNG TÌM THẤY PYTHON 3."
  read -r -p "Nhấn Enter để đóng..."
  exit 1
fi

python3 "scripts/update-site.py"
status=$?
echo
read -r -p "Nhấn Enter để đóng..."
exit "$status"

#!/usr/bin/env bash
set -euo pipefail

START_STAGE="${1:-generate}"
MODE="${2:-parallel}"
SOURCE="${3:-resume-script}"
BASE_URL="${NEWS_ECOSYSTEM_BASE_URL:-http://127.0.0.1:8010}"

python3 - "$START_STAGE" "$MODE" "$SOURCE" "$BASE_URL" <<'PY'
import json
import sys
from urllib import request

start_stage = sys.argv[1]
mode = sys.argv[2]
source = sys.argv[3]
base_url = sys.argv[4].rstrip("/")

all_stages = ["hot_api", "sort", "search", "generate", "review", "report"]
if start_stage not in all_stages:
    raise SystemExit(f"Unsupported start stage: {start_stage}")

payload = {
    "mode": mode,
    "source": source,
    "stages": all_stages[all_stages.index(start_stage):],
    "resume": True,
}

req = request.Request(
    f"{base_url}/api/ecosystem/runs",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
    method="POST",
)
with request.urlopen(req, timeout=30) as response:
    print(response.read().decode("utf-8"))
PY

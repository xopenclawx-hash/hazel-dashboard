#!/bin/bash
# 更新 Hazel 状态面板的时间戳
# 用法: update-status.sh <module> [summary] [details_json]
# 模块: btc, report, kb, security, cron, health

STATUS_FILE="/Users/rickywang/Projects/hazel-demo/status.json"
MODULE="$1"
SUMMARY="$2"
DETAILS="$3"
NOW=$(TZ='America/New_York' date '+%m-%d %H:%M')

if [ -z "$MODULE" ]; then
  echo "Usage: update-status.sh <btc|report|kb|security|cron|health> [summary] [details_json]"
  exit 1
fi

# 更新 JSON
python3 -c "
import json, sys
with open('$STATUS_FILE', 'r') as f:
    data = json.load(f)
module = '$MODULE'
if module not in data:
    data[module] = {}
data[module]['lastUpdate'] = '$NOW'
summary = '''$SUMMARY'''
if summary:
    data[module]['summary'] = summary
details = '''$DETAILS'''
if details:
    try:
        data[module]['details'] = json.loads(details)
    except json.JSONDecodeError as e:
        print(f'Warning: invalid details JSON: {e}', file=sys.stderr)
with open('$STATUS_FILE', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"

echo "Updated $MODULE: $NOW"

# 自动推送到 GitHub Pages
cd /Users/rickywang/Projects/hazel-demo
git add -A
git commit -m "Update $MODULE: $NOW" --quiet 2>/dev/null
git push --quiet 2>/dev/null &

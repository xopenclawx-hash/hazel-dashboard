#!/bin/bash
# 更新 Hazel 状态面板的时间戳
# 用法: update-status.sh <module> [summary]
# 模块: btc, report, kb, security, cron, health

STATUS_FILE="/Users/rickywang/Projects/hazel-demo/status.json"
HTML_FILE="/Users/rickywang/Projects/hazel-demo/index.html"
MODULE="$1"
SUMMARY="$2"
NOW=$(TZ='America/New_York' date '+%m-%d %H:%M')

if [ -z "$MODULE" ]; then
  echo "Usage: update-status.sh <btc|report|kb|security|cron|health> [summary]"
  exit 1
fi

# 更新 JSON
python3 -c "
import json
with open('$STATUS_FILE', 'r') as f:
    data = json.load(f)
module = '$MODULE'
if module not in data:
    data[module] = {}
data[module]['lastUpdate'] = '$NOW'
summary = '$SUMMARY'
if summary:
    data[module]['summary'] = summary
with open('$STATUS_FILE', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
"

# 更新 HTML 中对应的时间标签
sed -i '' "s|id=\"ts-$MODULE\">上次更新：[^<]*<|id=\"ts-$MODULE\">上次更新：$NOW<|" "$HTML_FILE"

echo "Updated $MODULE: $NOW"

# 自动推送到 GitHub Pages
cd /Users/rickywang/Projects/hazel-demo
git add -A
git commit -m "Update $MODULE: $NOW" --quiet 2>/dev/null
git push --quiet 2>/dev/null &

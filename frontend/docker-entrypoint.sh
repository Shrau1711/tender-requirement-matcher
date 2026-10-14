#!/bin/sh
# Runs when the container starts: tell the page where the backend is.
set -eu
url="${API_URL:-http://localhost:8000}"
case "$url" in
  *\"*|*\\*|*\<*|*\>*) echo "API_URL must not contain quotes, backslashes or angle brackets: $url" >&2; exit 1 ;;
esac
printf 'window.APP_CONFIG = { apiUrl: "%s" };\n' "$url" > /usr/share/nginx/html/config.js
echo "Frontend will call the backend at $url"

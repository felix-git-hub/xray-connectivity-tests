#!/bin/sh
# Run on wrt1k while the selected Actions job is waiting.
set -eu
case "${1:-}" in
  6h) port=1089 ;;
  2h) port=1090 ;;
  c2) port=2082 ;;
  c6) port=2083 ;;
  *) echo "Usage: sh verify-wrt1k.sh {6h|2h|c2|c6}" >&2; exit 2 ;;
esac
get() {
  curl -fsS --noproxy '' --proxy "socks5h://192.168.3.20:$port" --max-time 3 "http://127.0.0.1:18080/$1"
}
end=$(( $(date +%s) + 145 ))
while [ "$(date +%s)" -lt "$end" ]; do
  token=$(get "$1/challenge" 2>/dev/null) || token=''
  if [ "${#token}" -eq 64 ]; then
    case "$token" in
      *[!a-f0-9]*) ;;
      *) if [ "$(get "$1/confirm/$token")" = ok ]; then echo "$1 port $port verified"; exit 0; fi ;;
    esac
  fi
  sleep 1
done
echo "$1 port $port timed out" >&2
exit 1

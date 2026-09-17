#!/usr/bin/env bash
pkill -f "[d]ashd" 2>/dev/null
pkill -f "[d]ashboard/server.py" 2>/dev/null
sleep 2
setsid nohup bash /mnt/local/gakumas/scripts/dashd2.sh \
  > /mnt/local/gakumas/logs/dashd2.log 2>&1 < /dev/null &
sleep 12
echo "=== supervisor ==="; pgrep -fc "[d]ashd2.sh"
echo "=== dashboard ==="; pgrep -af "[d]ashboard/server.py" | head -2
echo "=== listening ==="; ss -ltn | grep 8900 || echo "NOT LISTENING"
echo "=== http ==="; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8900/ || true
echo "=== supervisor log ==="; tail -4 /mnt/local/gakumas/logs/dashd2.log

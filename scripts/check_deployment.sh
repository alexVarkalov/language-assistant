#!/usr/bin/env bash
#
# Post-deploy smoke check for one deployment, run on the host that serves it:
#
#     bash scripts/check_deployment.sh                        # language-assistant on :8080
#     bash scripts/check_deployment.sh language-assistant-ru-en 8081
#
# Exit status 0 means the deployment is healthy right now; 1 means something needs attention.
#
# The interesting check is the journal one. A bot can be `active` and still be broken at the edges:
# the AttributeError that `job_queue.scheduler.configure()` used to raise only ever appeared while the
# *previous* process was shutting down, so `systemctl restart` swallowed it and left the unit active.
# That is why the journal window starts before the unit did — a restart's stop half has to be inside it.

set -uo pipefail

NAME=${1:-language-assistant}
PORT=${2:-8080}
# due_poll is registered with first=10, so give it a little longer than that after a fresh start.
WAIT_SECONDS=${CHECK_WAIT_SECONDS:-45}
# How far before the unit's start to begin reading the journal, to cover the previous process's exit.
LOOKBEHIND=${CHECK_LOOKBEHIND:-2 minutes}

BOT="${NAME}-bot"
API="${NAME}-api"
failures=0

# Colour only for a human at a terminal: this output also gets piped into Telegram alerts by the
# monitoring cron, where escape codes are just noise.
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_BAD=$'\033[31m'; C_OFF=$'\033[0m'
else
    C_OK=''; C_WARN=''; C_BAD=''; C_OFF=''
fi

ok()   { printf '  %sok%s      %s\n' "$C_OK" "$C_OFF" "$1"; }
warn() { printf '  %swarn%s    %s\n' "$C_WARN" "$C_OFF" "$1"; }
bad()  { printf '  %sFAIL%s    %s\n' "$C_BAD" "$C_OFF" "$1"; failures=$((failures + 1)); }

# Start of the journal window for a unit: its start time minus LOOKBEHIND, in the host's local time
# (which is what journalctl --since expects). Falls back to a fixed window if the unit never started.
journal_since() {
    local unit=$1 started
    started=$(systemctl show "$unit" -p ExecMainStartTimestamp --value 2>/dev/null)
    if [ -n "$started" ] && date -d "$started - $LOOKBEHIND" '+%Y-%m-%d %H:%M:%S' 2>/dev/null; then
        return 0
    fi
    date -d "-15 minutes" '+%Y-%m-%d %H:%M:%S'
}

echo "== ${NAME} (api :${PORT}) =="

# 1) Both units are running.
for unit in "$BOT" "$API"; do
    state=$(systemctl is-active "$unit" 2>/dev/null)
    if [ "$state" = "active" ]; then
        ok "$unit is active"
    else
        bad "$unit is ${state:-unknown} (systemctl status $unit)"
    fi
    restarts=$(systemctl show "$unit" -p NRestarts --value 2>/dev/null)
    if [ -n "$restarts" ] && [ "$restarts" != "0" ]; then
        warn "$unit has auto-restarted ${restarts}x since its last manual start"
    fi
done

# 2) The API answers on its own port, behind nginx or not.
if health=$(curl -fsS --max-time 10 "http://127.0.0.1:${PORT}/api/health" 2>&1) &&
    printf '%s' "$health" | grep -q '"status":[[:space:]]*"ok"'; then
    ok "GET /api/health -> $health"
else
    bad "GET http://127.0.0.1:${PORT}/api/health -> ${health:-no response}"
fi

# 3) Neither unit logged an error, including while the previous process was shutting down.
for unit in "$BOT" "$API"; do
    since=$(journal_since "$unit")
    errors=$(journalctl -u "$unit" --since "$since" --no-pager -q 2>/dev/null |
        grep -c -e 'Traceback (most recent call last)' -e ' - ERROR - ' -e "Failed with result")
    if [ "${errors:-0}" -eq 0 ]; then
        ok "$unit journal clean since $since"
    else
        bad "$unit logged $errors error line(s) since $since (journalctl -u $unit --since '$since')"
    fi
done

# 4) The reminder job is actually firing — the bot can accept updates with a dead job queue.
since=$(journal_since "$BOT")
deadline=$((SECONDS + WAIT_SECONDS))
while :; do
    # grep -c, not grep -q: -q exits early, journalctl dies of SIGPIPE, and `pipefail` would then report
    # the successful match as a failed pipeline.
    polls=$(journalctl -u "$BOT" --since "$since" --no-pager -q 2>/dev/null |
        grep -c 'Job "due_poll.*executed successfully')
    if [ "${polls:-0}" -gt 0 ]; then
        ok "due_poll has executed ${polls}x since $since"
        break
    fi
    if [ "$SECONDS" -ge "$deadline" ]; then
        bad "no successful due_poll run in the last ${WAIT_SECONDS}s — reminders are not going out"
        break
    fi
    sleep 5
done

if [ "$failures" -eq 0 ]; then
    printf '\n%sPASS%s — %s looks healthy\n' "$C_OK" "$C_OFF" "$NAME"
else
    printf '\n%sFAIL%s — %s: %s check(s) need attention\n' "$C_BAD" "$C_OFF" "$NAME" "$failures"
fi
exit $(( failures > 0 ))

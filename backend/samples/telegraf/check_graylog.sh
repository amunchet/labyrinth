#!/bin/sh
# check_graylog - Telegraf exec check: is rsyslog installed, running, and
# successfully forwarding logs to Graylog?  Prints one Influx line-protocol
# point named "check_graylog" with ok=1i when everything looks healthy.
#
# Usage: check_graylog.sh [graylog_host[:port]]
#   The expected Graylog target can also come from $GRAYLOG_TARGET.  With
#   neither, the first forwarding target found in the rsyslog config is used.
#
# Telegraf:
#   [[inputs.exec]]
#     commands = ["/usr/local/bin/check_graylog.sh"]
#     timeout = "15s"
#     data_format = "influx"
#
# Suspended-forwarding detection reads the journal / syslog, so the telegraf
# user should be in the "adm" (and "systemd-journal") group.

PATH="$PATH:/usr/sbin:/sbin"
expected="${1:-$GRAYLOG_TARGET}"
root="${RSYSLOG_ROOT:-}"

installed=0
active=0
forwarding=0
reachable=0
reachability_checked=0
suspended=0
proto=""
host=""
port=""

if command -v rsyslogd >/dev/null 2>&1; then
    installed=1
fi

if systemctl is-active --quiet rsyslog 2>/dev/null     || cat /proc/[0-9]*/comm 2>/dev/null | grep -qx rsyslogd; then
    active=1
fi

# Every forwarding target as "proto host port", from both legacy selector
# syntax (*.* @@graylog:514) and RainerScript action(type="omfwd" ...).
confs=$(ls "$root"/etc/rsyslog.conf "$root"/etc/rsyslog.d/*.conf 2>/dev/null)
targets=""
if [ -n "$confs" ]; then
    stripped=$(cat $confs | sed 's/#.*//')
    legacy=$(echo "$stripped" \
        | grep -oE '(^|[[:space:];])@@?(\([^)]*\))?[A-Za-z0-9._-]+(:[0-9]+)?' \
        | sed -E 's/^[[:space:];]*//' \
        | while read -r t; do
            p=udp
            case "$t" in @@*) p=tcp ;; esac
            t=$(echo "$t" | sed -E 's/^@@?(\([^)]*\))?//')
            h=${t%%:*}
            pt=514
            [ "$h" != "$t" ] && pt=${t##*:}
            echo "$p $h $pt"
        done)
    rainer=$(echo "$stripped" | tr '\n' ' ' \
        | grep -oE 'action\([^)]*omfwd[^)]*\)' \
        | while read -r a; do
            h=$(echo "$a" | sed -nE 's/.*[Tt]arget="([^"]*)".*/\1/p')
            pt=$(echo "$a" | sed -nE 's/.*[Pp]ort="([^"]*)".*/\1/p')
            p=$(echo "$a" | sed -nE 's/.*[Pp]rotocol="([^"]*)".*/\1/p' | tr 'A-Z' 'a-z')
            [ -n "$h" ] && echo "${p:-udp} $h ${pt:-514}"
        done)
    targets=$(printf '%s\n%s\n' "$legacy" "$rainer" | sed '/^$/d')
fi

if [ -n "$expected" ]; then
    want_host=${expected%%:*}
    want_port=""
    [ "$want_host" != "$expected" ] && want_port=${expected##*:}
    chosen=$(echo "$targets" | awk -v h="$want_host" -v p="$want_port" \
        'tolower($2) == tolower(h) && (p == "" || $3 == p) { print; exit }')
else
    chosen=$(echo "$targets" | head -n 1)
fi

if [ -n "$chosen" ]; then
    forwarding=1
    set -- $chosen
    proto=$1
    host=$2
    port=$3
fi

# UDP can't be probed, so only check the target resolves; TCP gets a connect.
if [ "$forwarding" = 1 ]; then
    if [ "$proto" = tcp ]; then
        if command -v nc >/dev/null 2>&1; then
            reachability_checked=1
            nc -z -w 3 "$host" "$port" >/dev/null 2>&1 && reachable=1
        elif command -v bash >/dev/null 2>&1; then
            reachability_checked=1
            timeout 3 bash -c "exec 3<>/dev/tcp/$host/$port" >/dev/null 2>&1 && reachable=1
        fi
    fi
    if [ "$reachability_checked" = 0 ]; then
        getent hosts "$host" >/dev/null 2>&1 && reachable=1
        echo "$host" | grep -qE '^[0-9.]+$' && reachable=1
    fi
fi

# rsyslog logs "action ... suspended" when it gives up on a destination and
# "action ... resumed" once it recovers - whichever came last wins.
last=$( (journalctl -u rsyslog --since "-1h" --no-pager -q 2>/dev/null
         tail -n 2000 /var/log/syslog /var/log/messages 2>/dev/null) \
    | grep -E "action .*(suspended|resumed)" | tail -n 1)
case "$last" in *suspended*) suspended=1 ;; esac

if [ "$installed" = 0 ]; then
    status="rsyslog not installed"
elif [ "$active" = 0 ]; then
    status="rsyslog not running"
elif [ "$forwarding" = 0 ] && [ -n "$expected" ]; then
    status="rsyslog not forwarding to $expected"
elif [ "$forwarding" = 0 ]; then
    status="rsyslog not forwarding anywhere"
elif [ "$reachable" = 0 ]; then
    status="$host:$port unreachable"
elif [ "$suspended" = 1 ]; then
    status="rsyslog forwarding suspended"
else
    status="ok"
fi

ok=0
[ "$status" = ok ] && ok=1

tags=""
[ "$forwarding" = 1 ] && tags=",target=$host:$port,protocol=$proto"

echo "check_graylog$tags ok=${ok}i,installed=${installed}i,active=${active}i,forwarding=${forwarding}i,target_reachable=${reachable}i,reachability_checked=${reachability_checked}i,suspended=${suspended}i,status=\"$status\""

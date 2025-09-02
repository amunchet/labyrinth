import json
import redis
import os

from ai import chatgpt_helper
from ai import email_helper
from ai import slack_helper


from dotenv import load_dotenv

load_dotenv()


def process_dashboard(testing=False):
    """
    Return failing hosts in slimmed-down format:
    [
        [ip_or_host, [name, {slimmed svc}], name, {slimmed svc}, ...],
        ...
    ]
    """
    if testing:
        data = testing
    else:  # pragma: no cover
        rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
        cachedboard = rc.get("dashboard")

        if not cachedboard:
            return "No dashboard"

        data = json.loads(cachedboard.decode())

    results = []

    # keep only the bits we actually use to make a judgement
    FOUND_KEEP = (
        "display_name",
        "name",
        "metric",
        "comparison",
        "value",
        "tag_name",
        "tag_value",
    )
    METRIC_FIELDS_KEEP = (
        "service_output",
        "long_service_output",
        "state",
        "http_response_code",
        "status_code",
        "result_code",
        "result_type",
        "response_time",
        "content_length",
        "ports",
        "ip",
    )
    METRIC_TAGS_KEEP = ("server", "status_code", "method", "result", "host", "ip")

    def slim_found_service(found):
        if isinstance(found, str):
            return {"name": found}
        if isinstance(found, dict):
            return {k: found.get(k) for k in FOUND_KEEP if k in found}
        return None

    def slim_latest_metric(m):
        if not isinstance(m, dict):
            return None
        out = {}
        # keep metric name + timestamp if present
        n = m.get("name")
        if n:
            out["name"] = n
        ts = m.get("timestamp")
        if ts is not None:
            out["timestamp"] = ts
        # keep only key signal fields
        f = m.get("fields")
        if isinstance(f, dict):
            out["fields"] = {k: f.get(k) for k in METRIC_FIELDS_KEEP if k in f}
        t = m.get("tags")
        if isinstance(t, dict):
            kept_tags = {k: t.get(k) for k in METRIC_TAGS_KEEP if k in t}
            if kept_tags:
                out["tags"] = kept_tags
        return out or None

    for dash in data:
        for group in dash.get("groups", []):
            for host in group.get("hosts", []):
                # skip if not monitored or downgraded to warning at host level
                if not host.get("monitor"):
                    continue
                if host.get("service_level") == "warning":
                    continue

                # set of services that are allowed to be 'warning' without counting as failing
                warning_services = {
                    (lvl.get("service") or "").strip()
                    for lvl in host.get("service_levels", [])
                    if (lvl.get("level") or "").strip().lower() == "warning"
                }

                failing = []
                for svc in host.get("services", []):
                    # figure out a human name for the service
                    name = (svc.get("name") or "").strip()
                    if not name:
                        found = svc.get("found_service")
                        if isinstance(found, str):
                            name = found.strip()
                        elif isinstance(found, dict):
                            name = (
                                (found.get("display_name") or found.get("name") or "")
                            ).strip()

                    # only consider hard failures; ignore 'new_host' and services lowered to 'warning'
                    if (
                        name
                        and svc.get("state") is False
                        and name not in warning_services
                        and name != "new_host"
                        and name != "open_ports"
                        and name != "closed_ports"
                    ):
                        # append the readable name
                        failing.append(name)

                        # append a slimmed dict with just the judgement-critical bits
                        slim = {
                            "state": False,
                        }
                        sf = slim_found_service(svc.get("found_service"))
                        if sf:
                            slim["found_service"] = sf
                        lm = slim_latest_metric(svc.get("latest_metric"))
                        if lm:
                            slim["latest_metric"] = lm

                        failing.append(slim)

                if failing:
                    # prefer 'host' if populated, otherwise fall back to ip
                    host_key = (host.get("host") or "").strip() or host.get("ip")
                    results.append([host_key, failing])

    return json.dumps(results).replace(" ", "")


def main(prompt_filename="initial_prompt.txt"):
    """
    Main process runner
    """

    # Read in from Redis
    first_pass = process_dashboard()

    # Pass through ChatGPT
    with open(os.path.join("ai", prompt_filename)) as f:
        initial_prompt = f.read()

    output = chatgpt_helper.ml_process(first_pass, initial_prompt)

    # Determine if we need to send email
    output = output.json()
    output = output["choices"][0]["message"]["content"]
    output = json.loads(output)

    rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")

    # Helper: build a set of (host, service) from current output
    def _pairs_set_from_crit(crit):
        s = set()
        for item in crit or []:
            h = item.get("host"); sv = item.get("service_name")
            if h is not None and sv is not None:
                s.add((str(h).lower(), str(sv).lower()))  # case-insensitive
        return s

    # Helper: parse stored normalized pairs JSON -> set of tuples
    def _pairs_set_from_norm(norm_str):
        try:
            data = json.loads(norm_str)
            pairs = set()
            for it in data:
                if isinstance(it, (list, tuple)) and len(it) == 2:
                    pairs.add((str(it[0]).lower(), str(it[1]).lower()))
            return pairs
        except Exception:
            return set()

    TTL_SECONDS = int(os.environ.get("ALERT_TTL_SECONDS", "7200"))

    if output.get("wake_up_it_director"):
        print("Waking Up IT Director...")
        try:
            last_email_raw = rc.get("last_email")
        except Exception as e:  # pragma: no cover
            print("Warning: Redis get failed:", e)
            last_email_raw = None

        current_set = _pairs_set_from_crit(output.get("critical_services"))
        current_norm = json.dumps(sorted(list(current_set)), separators=(",", ":"))

        # last_norm may be absent on first run
        last_norm = None
        if last_email_raw:
            decoded = last_email_raw.decode("utf-8")
            # accept only valid JSON; legacy handled by _pairs_set_from_norm
            try:
                json.loads(decoded)
                last_norm = decoded
            except Exception:  # pragma: no cover
                last_norm = None

        last_set = _pairs_set_from_norm(last_norm) if last_norm else set()

        # ✅ Only new problems (present now but not in last state)
        new_issues = current_set - last_set

        if (not last_norm) or new_issues:
            if new_issues:
                print("New critical issues since last email:", sorted(list(new_issues)))
            else:
                print("First run (no baseline); sending email.")

            msg_id = email_helper.email_helper(
                to=[os.environ.get("EMAIL_TO")],
                subject="Labyrinth IT AI ALERT",
                html=output.get("summary_email", "See HTML version"),
                text="See HTML version",
                attachments=None,
                from_name="Labyrinth AI",
            )
            print("Message-ID:", msg_id)
        else:
            print("No NEW critical issues since last email")

        # Always update baseline to current state so reappearances trigger later
        try:
            rc.setex("last_email", TTL_SECONDS, current_norm)
        except Exception as e:  # pragma: no cover
            print("Warning: Redis setex failed:", e)
    else:
        print("wake_up_it_director = False; no email sent.")


if __name__ == "__main__":  # pragma: no cover
    main()

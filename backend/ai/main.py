import json
import redis

# Filtered Dashboard - AI
# @requires_auth_read
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
    else: # pragma: no cover
        rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")
        cachedboard = rc.get("dashboard")

        if not cachedboard:
            return "No dashboard"

        data = json.loads(cachedboard.decode())

    results = []

    # keep only the bits we actually use to make a judgement
    FOUND_KEEP = ("display_name", "name", "metric", "comparison", "value", "tag_name", "tag_value")
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
                            name = ((found.get("display_name") or found.get("name") or "")).strip()

                    # only consider hard failures; ignore 'new_host' and services lowered to 'warning'
                    if (
                        name
                        and svc.get("state") is False
                        and name not in warning_services
                        and name != "new_host"
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

    return json.dumps(results, indent=2)

if __name__ == "__main__":
    with open("sample.json") as f:
        process_dashboard(json.load(f))
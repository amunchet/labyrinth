import json
import redis
import os
from datetime import datetime

from ai import email_helper
from ai import slack_helper
from ai.ai_settings import (
    DEFAULT_AI_PROMPT,
    DEFAULT_AI_MODEL,
    DEFAULT_AI_ALERT_SUBJECT_TEMPLATE,
    DEFAULT_AI_ALERT_FROM_NAME,
    get_ai_alert_settings,
    get_mongo_client,
)
from ai.ai_pipeline import (
    process_dashboard,
    render_email_html,
    render_alert_email_html,
    run_ai_judgement,
)


from dotenv import load_dotenv

load_dotenv()


def main(initial_prompt="", db=None):
    """
    Main process runner
    """

    db = db or get_mongo_client()
    ai_settings = get_ai_alert_settings(db)

    # An explicit initial_prompt wins (used by tests); otherwise use the
    # prompt configured under Settings -> AI Alerts (backed by Mongo, with a
    # built-in default for fresh installs - see get_ai_alert_settings).
    prompt = initial_prompt or ai_settings["prompt"]

    output = run_ai_judgement(prompt, ai_settings["model"])

    rc = redis.Redis(host=os.environ.get("REDIS_HOST") or "redis")

    # Helper: build a set of (host, service) from current output
    def _pairs_set_from_crit(crit):
        s = set()
        for item in crit or []:
            h = item.get("host")
            sv = item.get("service_name")
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

            if not ai_settings["recipients"]:
                print("No AI alert recipients configured; skipping email.")
            else:
                subject = ai_settings["subject_template"].replace(
                    "{time}", datetime.now().strftime("%Y-%m-%d %H:00")
                )
                msg_id = email_helper.email_helper(
                    to=ai_settings["recipients"],
                    subject=subject,
                    html=render_alert_email_html(output),
                    text="See HTML version",
                    attachments=None,
                    from_name=ai_settings["from_name"],
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
        print(output)


if __name__ == "__main__":  # pragma: no cover
    main()

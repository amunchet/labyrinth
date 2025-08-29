# utils.py
# Basic utility functions that don't belong in serve
import serve
from datetime import datetime, timezone
from pymongo import UpdateOne

def update_service_expire_dates():
    """
    Finds all hosts with a service_level_expire_date.
    - If a host's date is expired, then remove it (delete `service_level_expire_date` and `service_level`).
    """

    coll = serve.mongo_client["labyrinth"]["hosts"]

    # Find all docs where the field is present
    hosts_with_expire_date = list(
        coll.find({"service_level_expire_date": {"$exists": True}})
    )

    if not hosts_with_expire_date:
        return 0  # nothing to do

    now = datetime.now(timezone.utc)

    bulk_ops = []
    for host in hosts_with_expire_date:
        expire_date = host.get("service_level_expire_date")
        if expire_date is None:
            continue

        # Normalize to datetime if stored as string
        if isinstance(expire_date, str):
            try:
                expire_date = datetime.fromisoformat(expire_date)
            except ValueError:
                # Skip invalid format
                continue

        # If expired -> prepare update
        if isinstance(expire_date, datetime) and expire_date < now:
            print("Deleting", host["_id"], ":", expire_date)
            bulk_ops.append(
                UpdateOne(
                    {"_id": host["_id"]},
                    {"$unset": {"service_level_expire_date": "", "service_level": ""}},
                )
            )

    if bulk_ops:
        result = coll.bulk_write(bulk_ops)
        return result.modified_count

    return 0

if __name__ == "__main__": # pragma: no cover
    update_service_expire_dates()
#!/usr/bin/env python3
"""Refresh cached Proxmox disk-space payloads in Redis."""

import json

from pid import PidFile

import proxmox_helper
from serve import mongo_client


def refresh_proxmox_cache():  # pragma: no cover
    """Refresh Redis-backed Proxmox cache for all configured clusters."""
    with PidFile("labyrinth-proxmox-refresh"):
        clusters = list(mongo_client["labyrinth"]["proxmox_clusters"].find({}))
        redis_client = proxmox_helper.get_redis_client()
        results = proxmox_helper.refresh_proxmox_cluster_cache(clusters, redis_client=redis_client)

        print(
            json.dumps(
                {
                    "status": "ok",
                    "clusters": len(clusters),
                    "refreshed": len(results),
                }
            )
        )


if __name__ == "__main__":  # pragma: no cover
    refresh_proxmox_cache()

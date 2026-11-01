#!/usr/bin/env python3
"""
MCP client tools beyond hosts/services: location maps and their images,
subnets and groups, tags and service levels, alerts and monitoring reports.
"""

import io
import json
import os
from unittest.mock import patch

import pytest
from PIL import Image

import serve
from ai.mcp.client import IMAGES_DIR, LabyrinthClient
from common.test import unwrap

IMAGE = "test_29_floorplan.png"


def tearDown():
    for collection in ["hosts", "subnets", "locations", "dashboards"]:
        serve.db["labyrinth"][collection].delete_many({})
    if os.path.exists(os.path.join(IMAGES_DIR, IMAGE)):
        os.remove(os.path.join(IMAGES_DIR, IMAGE))


@pytest.fixture
def client():
    tearDown()
    unwrap(serve.create_edit_location)({"name": "North", "racks": []})
    for host in [
        {"ip": "192.168.9.6", "mac": "aa:01", "host": "Central Bay Switch"},
        {"ip": "192.168.11.105", "mac": "aa:02", "host": "Loading Dock"},
        {"ip": "", "mac": "", "host": "Patch panel"},
    ]:
        assert unwrap(serve.create_edit_host)({"services": [], **host})[1] == 200
    os.makedirs(IMAGES_DIR, exist_ok=True)
    # A transparent floor plan with one red room in the top-left corner
    img = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (0, 0, 100, 100))
    img.save(os.path.join(IMAGES_DIR, IMAGE))
    yield LabyrinthClient()
    tearDown()


def test_map_create_place_and_move(client):
    saved = client.save_map(
        {"name": "North Floor", "location": "north", "background_image": IMAGE}
    )
    # Location names are matched case-insensitively and stored as defined
    assert saved["location"] == "North"
    assert saved["placements"] == []

    # Devices can be given by IP; positions are rounded percentages
    placed = client.place_devices(
        "North Floor",
        [
            {"key": "192.168.9.6", "x": 50.123, "y": 40},
            {"key": "aa:02", "x": 90, "y": 10},
        ],
        [],
    )
    assert [(x["key"], x["x"], x["y"]) for x in placed["placements"]] == [
        ("aa:01", 50.12, 40.0),
        ("aa:02", 90.0, 10.0),
    ]
    assert placed["placements"][0]["device"]["name"] == "Central Bay Switch"

    # Moving one device and removing another leaves nothing else changed
    moved = client.place_devices(
        "North Floor", [{"key": "aa:01", "x": 10, "y": 20}], ["192.168.11.105"]
    )
    assert [(x["key"], x["x"]) for x in moved["placements"]] == [("aa:01", 10.0)]

    # The stored map is what the frontend reads: no device details persisted
    stored = serve.db["labyrinth"]["dashboards"].find_one({"name": "North Floor"})
    assert stored["placements"] == [{"key": "aa:01", "x": 10.0, "y": 20.0}]
    assert stored["background_image"] == IMAGE

    assert client.list_maps("NORTH") == [
        {
            "name": "North Floor",
            "location": "North",
            "background_image": IMAGE,
            "default": False,
            "placed": 1,
            "legacy": False,
        }
    ]
    assert client.list_maps("South") == []


@pytest.mark.parametrize(
    "placement, problem",
    [
        ({"key": "10.9.9.9", "x": 1, "y": 1}, "No device"),
        ({"key": "aa:01", "x": 101, "y": 1}, "within 0-100"),
        ({"key": "aa:01", "x": "left", "y": 1}, "numeric"),
        ({"key": "aa:01", "y": 1}, "numeric"),
    ],
)
def test_bad_placements_are_refused(client, placement, problem):
    client.save_map({"name": "Floor"})
    with pytest.raises(ValueError, match=problem):
        client.place_devices("Floor", [placement], [])
    assert (
        serve.db["labyrinth"]["dashboards"].find_one({"name": "Floor"})["placements"]
        == []
    )


def test_save_map_refuses_unknown_references(client):
    with pytest.raises(ValueError, match="No location"):
        client.save_map({"name": "Floor", "location": "Mars"})
    with pytest.raises(ValueError, match="No uploaded image"):
        client.save_map({"name": "Floor", "background_image": "missing.png"})
    with pytest.raises(ValueError, match="needs a name"):
        client.save_map({"name": " "})
    assert client.list_maps() == []


def test_update_keeps_fields_rename_and_single_default(client):
    client.save_map({"name": "A", "default": True, "location": "North"})
    client.place_devices("A", [{"key": "aa:01", "x": 1, "y": 2}], [])
    client.save_map({"name": "B", "default": True})

    maps = {x["name"]: x for x in client.list_maps()}
    assert not maps["A"]["default"] and maps["B"]["default"]
    # Fields left out of the update were kept
    assert maps["A"]["location"] == "North" and maps["A"]["placed"] == 1

    renamed = client.save_map({"name": "A2", "previous_name": "A"})
    assert renamed["placements"][0]["key"] == "aa:01"
    assert sorted(x["name"] for x in client.list_maps()) == ["A2", "B"]

    with pytest.raises(ValueError, match="already exists"):
        client.save_map({"name": "B", "previous_name": "A2"})
    with pytest.raises(ValueError, match="No map named"):
        client.save_map({"name": "C", "previous_name": "nope"})

    assert client.delete_map("A2") == "Success"
    with pytest.raises(ValueError, match="No map named"):
        client.delete_map("A2")


def test_deleted_device_shows_as_missing_and_can_be_removed(client):
    client.save_map({"name": "Floor"})
    client.place_devices("Floor", [{"key": "aa:02", "x": 5, "y": 5}], [])
    # Bypass delete_host, which would also drop the placement
    serve.db["labyrinth"]["hosts"].delete_one({"mac": "aa:02"})

    assert client.get_map("Floor")["placements"][0]["device"] is None
    assert client.place_devices("Floor", [], ["aa:02"])["placements"] == []


def test_legacy_map_is_flagged(client):
    serve.db["labyrinth"]["dashboards"].insert_one({"name": "Old", "components": []})
    assert client.list_maps()[0]["legacy"] is True


def test_map_image_is_scaled_jpeg_on_white(client):
    assert IMAGE in client.list_map_images()
    img = Image.open(io.BytesIO(client.get_map_image(IMAGE, max_size=200)))
    assert img.format == "JPEG" and img.size == (200, 100)
    red = img.getpixel((10, 10))
    paper = img.getpixel((150, 80))
    assert red[0] > 200 and red[1] < 60
    assert min(paper) > 240
    with pytest.raises(ValueError, match="No uploaded image"):
        client.get_map_image("../etc/passwd")


def test_tags_and_service_levels(client):
    assert client.set_host_tags("192.168.9.6", "core,poe")["tags"] == "core,poe"
    key = serve.db["labyrinth"]["hosts"].find_one({"host": "Patch panel"})["mac"]
    # IP-less devices are tagged through their full record
    assert client.set_host_tags(key, "passive")["tags"] == "passive"
    assert client.list_tags() == ["core", "passive", "poe"]
    assert [x["mac"] for x in client.list_hosts_by_tag("core")] == ["aa:01"]

    host = client.set_service_level("aa:01", "check_hd", "warning")
    assert host["service_levels"] == [{"service": "check_hd", "level": "warning"}]
    assert client.set_service_level("aa:01", "check_hd", "")["service_levels"] == []
    with pytest.raises(ValueError, match="level must be"):
        client.set_service_level("aa:01", "check_hd", "critical")
    with pytest.raises(ValueError, match="with an IP"):
        client.set_service_level(key, "check_hd", "error")

    assert client.delete_host("aa:02") == "Success"
    with pytest.raises(ValueError, match="Host not found"):
        client.delete_host("aa:02")


def test_subnets_and_groups(client):
    saved = client.save_subnet({"subnet": "192.168.9", "location": "North"})
    # Created by the host save, so its existing fields survive the update
    assert saved["location"] == "North" and saved["links"] == {}
    assert "192.168.9" in client.list_subnets()
    with pytest.raises(ValueError, match="needs its"):
        client.save_subnet({"location": "North"})

    serve.db["labyrinth"]["hosts"].update_one(
        {"mac": "aa:01"}, {"$set": {"group": "Switches"}}
    )
    assert client.list_groups("192.168.9") == [
        {"group": "Switches", "members": ["192.168.9.6"]}
    ]
    result = client.update_group(
        "192.168.9", "Switches", new_name="Core", monitor=True, add_service="ping"
    )
    assert result == {
        "subnet": "192.168.9",
        "group": "Core",
        "members": ["192.168.9.6"],
    }
    host = client.get_host("aa:01")
    assert host["monitor"] is True and host["services"] == ["ping"]
    client.update_group("192.168.9", "Core", monitor=False, remove_service="ping")
    host = client.get_host("aa:01")
    assert host["monitor"] is False and host["services"] == []
    with pytest.raises(ValueError, match="No group"):
        client.update_group("192.168.9", "Nope", icon="router")

    assert client.delete_subnet("192.168.9") == "Success"
    with pytest.raises(ValueError, match="No subnet"):
        client.get_subnet("192.168.9")
    with pytest.raises(ValueError, match="No subnet"):
        client.delete_subnet("192.168.9")


def test_resolve_alert_by_fingerprint():
    alerts = [{"fingerprint": "abc", "startsAt": "x", "labels": {"host": "sw"}}]
    with patch("serve.list_alerts") as list_alerts, patch(
        "serve.resolve_alert"
    ) as resolve_alert:
        list_alerts.__wrapped__ = lambda: (json.dumps(alerts), 200)
        resolve_alert.__wrapped__ = lambda data: (resolved.append(data) or "", 200)
        resolved = []
        assert LabyrinthClient().resolve_alert("abc") == "Success"
        assert resolved == alerts
        with pytest.raises(ValueError, match="No active alert"):
            LabyrinthClient().resolve_alert("zzz")


def test_route_failures_raise_with_their_message():
    with patch("serve.get_proxmox_disk_space") as handler:
        handler.__name__ = "get_proxmox_disk_space"
        handler.__wrapped__ = lambda: (json.dumps({"error": "Failed"}), 500)
        with pytest.raises(RuntimeError, match="get_proxmox_disk_space failed"):
            LabyrinthClient().get_proxmox_disk_space()


def test_reports_pass_through():
    client = LabyrinthClient()
    with patch("serve.get_proxmox_telegraf_check") as handler:
        # The handler reads its window from the query string
        handler.__wrapped__ = lambda: (
            json.dumps({"stale": serve.request.args.get("stale_minutes")}),
            200,
        )
        assert client.get_proxmox_telegraf_check(30) == {"stale": "30"}

    for name, method in [
        ("refresh_proxmox_disk_space", lambda: client.get_proxmox_disk_space(True)),
        ("get_proxmox_graylog_check", client.get_proxmox_graylog_check),
        ("list_proxmox_clusters", client.list_proxmox_clusters),
        ("get_aws_ec2_instances", client.get_ec2_instances),
        ("read_metric_counts", lambda: client.get_metric_counts("aa:01")),
        ("read_service", lambda: client.get_service("ping")),
    ]:
        with patch("serve." + name) as handler:
            handler.__wrapped__ = lambda *a: (json.dumps([{"ok": name}]), 200)
            result = method()
        # get_service unwraps the single match; the rest pass through as-is
        assert result in ([{"ok": name}], {"ok": name})

    with patch("serve.read_service") as handler:
        handler.__wrapped__ = lambda *a: ("[]", 200)
        with pytest.raises(ValueError, match="No service"):
            client.get_service("nope")

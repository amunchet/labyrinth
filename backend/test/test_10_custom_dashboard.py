#!/usr/bin/env python3

import os
import json
import shutil

import pytest
import serve

from copy import deepcopy

from common.test import unwrap

with open("test/sample_custom_dashboard.json") as f:
    SAMPLE_DASHBOARD = json.load(f)


def tearDown():
    """Tear down"""

    # Remove the images folder in uploads

    if os.path.exists("/src/uploads/images"):
        shutil.rmtree("/src/uploads/images")

    if os.path.exists("/tmp/floorplan.jpg"):
        os.remove("/tmp/floorplan.jpg")

    if os.path.exists("/tmp/broken.jpg"):
        os.remove("/tmp/broken.jpg")

    serve.mongo_client["labyrinth"]["dashboards"].delete_many({"name": "TESTTEST"})


@pytest.fixture
def setup():
    """Sets up"""
    tearDown()

    floorplan = "/src/test/images/floorplan.jpg"
    broken = "/src/test/images/broken.jpg"

    shutil.copy(floorplan, "/tmp/floorplan.jpg")
    shutil.copy(broken, "/tmp/broken.jpg")

    yield "Setting up"
    tearDown()
    return "Done"


# Main Dashboard
def test_create_edit_custom_dashboard(setup):
    """
    Creates of edits a custom dashboard main structure
        - Any edits of hosts/services will happen on frontend (e.g. moving X,Y around)

        - All images
        - Plugins (Services, hosts, etc.)
    """
    a = serve.mongo_client["labyrinth"]["dashboards"].find({"name": "TESTTEST"})
    assert not list(a)

    a = unwrap(serve.create_edit_custom_dashboard)("TESTTEST", data=SAMPLE_DASHBOARD)
    assert a[1] == 200

    a = serve.mongo_client["labyrinth"]["dashboards"].find({"name": "TESTTEST"})
    assert len(list(a)) == 1

    # Check that we edit on the same name, not create new
    temp = deepcopy(SAMPLE_DASHBOARD)
    temp["components"][0]["rotation"] = "vertical"

    a = unwrap(serve.create_edit_custom_dashboard)("TESTTEST", data=temp)
    assert a[1] == 200

    a = list(serve.mongo_client["labyrinth"]["dashboards"].find({"name": "TESTTEST"}))
    assert len(a) == 1
    print(a)
    assert a[0]["components"][0]["rotation"] == "vertical"


def test_list_and_delete_custom_dashboards(setup):
    """
    Lists all custom dashboards
    """
    a = unwrap(serve.list_custom_dashboards)()
    assert a[1] == 200
    assert [x for x in json.loads(a[0]) if "name" in x and x["name"] == "TESTTEST"] == []

    test_create_edit_custom_dashboard(setup)

    a = unwrap(serve.list_custom_dashboards)()
    assert a[1] == 200
    b = [x for x in json.loads(a[0]) if "name" in x and x["name"] == "TESTTEST"]
    assert len(b) == 1

    a = unwrap(serve.list_custom_dashboards)("TESSDFSDFS")
    assert a[1] == 404

    a = unwrap(serve.list_custom_dashboards)("TESTTEST")
    assert a[1] == 200
    assert json.loads(a[0])

    b = [x for x in json.loads(a[0]) if "name" in x and x["name"] == "TESTTEST"]
    assert len(b) == 1

    # Deletes a custom dashboard
    a = unwrap(serve.delete_custom_dashboard)("TESTTEST")
    assert a[1] == 200

    a = unwrap(serve.list_custom_dashboards)()

    assert a[1] == 200
    assert [x for x in json.loads(a[0]) if "name" in x and x["name"] == "TESTTEST"] == []

# Images
def test_image_upload(setup):
    """
    Tests image upload
        - This is separate from ansible upload
        - Main images and sub images
    """

    assert not os.path.exists("/src/uploads/images")

    a = unwrap(serve.custom_dashboard_image_upload)(
        override="floorplan.jpg"
    )
    assert a[1] == 200

    a = unwrap(serve.custom_dashboard_image_upload)(
        override="broken.jpg"
    )
    assert a[1] == 484

    assert os.path.exists("/src/uploads/images/floorplan.jpg")

    # Deletes an uploaded image

    a = unwrap(serve.custom_dashboard_delete_image)("../../test/images/broken.jpg")
    assert a[1] == 404

    a = unwrap(serve.custom_dashboard_delete_image)("floorplan.jpg")
    assert a[1] == 200

    assert not os.path.exists("/src/uploads/images/floorplan.jpg")


def test_images_list(setup):
    """
    Lists all uploaded images
    """
    a = unwrap(serve.custom_dashboard_list_images)()
    assert a[1] == 200
    assert json.loads(a[0]) == []

    a = unwrap(serve.custom_dashboard_image_upload)(
        override="floorplan.jpg"
    )
    assert a[1] == 200

    a = unwrap(serve.custom_dashboard_list_images)()
    assert a[1] == 200
    assert json.loads(a[0]) == ["floorplan.jpg"]

#!/usr/bin/env python3

import os
import json
import shutil

import pytest
import serve


from common.test import unwrap

with open("test/sample_custom_dashboard.json") as f:
    SAMPLE_DASHBOARD = json.load(f)

def tearDown():
    """Tear down"""
    serve.mongo_client["labyrinth"]["dashboards"].delete_many({"name" : "TESTTEST"})

    # TODO: Remove any extra images created

@pytest.fixture
def setup():
    """Sets up"""
    tearDown()

    # TODO: Create some image files
    # TODO: Also some invalid

    yield "Setting up"
    tearDown()
    return "Done"

# Main Dashboard
def test_create_edit_custom_dashboard(setup):
    """
    Creates of edits a custom dashboard main structure
        - Any edits of hosts/services will happen on frontend (e.g. moving X,Y around)
    """
    a = serve.mongo_client["labyrinth"]["dashboards"].find({"name" : "TESTTEST"})
    assert not list(a) 

    a = unwrap(serve.test_create_edit_custom_dashboard)(data=SAMPLE_DASHBOARD)
    assert a[1] == 200

    a = serve.mongo_client["labyrinth"]["dashboards"].find({"name" : "TESTTEST"})
    assert a[1] == 200

    # TODO: Check that we edit on the same name, not create new


def test_list_custom_dashboards(setup):
    """
    Lists all custom dashboards
    """
    a = unwrap(serve.test_list_custom_dashboards)()
    assert a[1] == 200
    assert [x for x in json.loads(a[0]) if "name" in x and x["name"] == "TESTTEST"] == []

    test_create_edit_custom_dashboard(setup)

    a = unwrap(serve.test_list_custom_dashboards)()
    assert a[1] == 200
    b = [x for x in json.loads(a[0]) if "name" in x and x["name"] == "TESTTEST"] 
    assert len(b) == 1



def test_delete_custom_dashboard(setup):
    """
    Deletes a custom dashboard
    """


# Images
def test_image_upload(setup):
    """
    Tests image upload
        - This is separate from ansible upload
        - Main images and sub images
    """

def test_image_delete(setup):
    """
    Deletes an uploaded image
    """

def test_images_list(setup):
    """
    Lists all uploaded images
    """


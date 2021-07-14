#!/usr/bin/env python3
"""
Tests receipt of input from things like Telegraf
"""
import pytest
import serve
from common.test import unwrap
sample_data = {
    "metrics": [
        {
            "fields": {
                "boot_time": 1625587759,
                "context_switches": 4143261228,
                "entropy_avail": 3760,
                "interrupts": 1578002983,
                "processes_forked": 884284
            },
            "name": "kernel",
            "tags": {
                "host": "aacd4239ee68"
            },
            "timestamp": 1625683390
        },
    ]
}

@pytest.fixture
def setup():
    serve.mongo_client["labyrinth"]["metrics"].delete_many({})
    yield "Setup"
    serve.mongo_client["labyrinth"]["metrics"].delete_many({})
    return "Finished"

def test_insert(setup):
    """Tests inserting into database"""
    try:
        serve.mongo_client["labyrinth"]["metrics"].drop_index("metrics.timestamp_1")
    except Exception:
        print("No index found.  Continuing.")

    a = unwrap(serve.insert_metric)(sample_data)
    assert a[1] == 200

    b = serve.mongo_client["labyrinth"]["metrics"].find({})
    c = [x for x in b]
    assert len(c) == 1
    assert c[0]["metrics"] == sample_data["metrics"]

    # Tests list of indexes
    indexes = [
        "metrics.timestamp_1"
    ]
    x = [x for x in serve.mongo_client["labyrinth"]["metrics"].index_information().keys()]
    for item in indexes:
        assert item in x
    
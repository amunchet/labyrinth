#!/usr/bin/env python3
"""
Redis tests:
    - Test redis reader (read_redis)
    - Test redis autosave (get_autosave)
"""
import pytest
import redis

import serve

from common.test import unwrap

def test_read_redis():

    a = redis.Redis(host="redis")
    temp = a.get("output")
    a.set("output", "test")

    b = unwrap(serve.read_redis)()
    assert b[1] == 200
    assert b[0] == b"test"

    a.set("output", temp)


def test_redis_autosave():
    """
    Tests redis autosave
    """
    client_id = "asdfasdfasdfasdf"
    a = redis.Redis(host="redis")
    temp = a.get(client_id)

    b = unwrap(serve.autosave)(client_id, "TEST")
    assert b[1] == 200
    assert a.get(client_id) == b"TEST"

    a.set(client_id, temp)

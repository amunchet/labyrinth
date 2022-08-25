"""
Tests index helper
"""
import json
import os

import pytest
import serve

from common.test import unwrap

def test_index_helper():
    """
    Tests index helper
    """
    # Remove all indexes and then check
    try:
        serve.mongo_client["labyrinth"]["metrics"].drop_index("timestamp_-1")
    except serve.pymongo.errors.OperationFailure:
        pass
    
    assert "timestamp_-1" not in str(list(serve.mongo_client["labyrinth"]["metrics"].list_indexes()))

    serve.index_helper()

    assert "timestamp_-1" in str(list(serve.mongo_client["labyrinth"]["metrics"].list_indexes()))

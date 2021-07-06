#!/usr/bin/env python3

"""Sample tests"""
import requests
def test_insecure():
    """Try to access open resource (success) and protected (fail)"""
    
    a = requests.get("http://localhost:7000/insecure")
    assert a.status_code == 200

def test_secure():
    """Checks access to a protected resource"""

    a = requests.get("http://localhost:7000/secure")
    assert a.status_code == 500 # Production would be 401
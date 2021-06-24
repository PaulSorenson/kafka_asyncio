#!/bin/env python3

"""
password discovery
"""

import os
from getpass import getpass

try:
    import keyring
except ImportError:
    print("no keyring module installed, password method not available.")


def get_password(username: str, service: str) -> str:
    """
    password discovery

    Try keyring: pip install keyring; keyring set service username
    Args:
        username: (username, service) key for password. These can be arbitrary
            strings, the function has no knowledge of the services themselves.
        service: see ^^^
    """
    try:
        password = keyring.get_password(service_name=service, username=username)
        if password is not None:
            return password
    except Exception:
        password = ""

    password = os.getenv(f"{service.upper()}_PASSWORD")
    if password == "":
        return password

    password = getpass(f"[{username}] enter password> ")

    return password

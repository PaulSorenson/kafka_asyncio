#!/bin/env python3

"""
create ssl.SSLContext for kafka clients.
"""

import logging
from importlib import resources
from pathlib import Path
from ssl import SSLContext

from aiokafka.helpers import create_ssl_context  # type: ignore

import webcheck

logging.basicConfig()
log = logging.getLogger()


CAFILE = Path("ca.pem")
CERTFILE = Path("service.cert")
KEYFILE = Path("service.key")


def get_kafka_ssl_context() -> SSLContext:
    """get kafka ssl context

    For this exercise we are packaging the ssl files in the python package.
    In real life these would come from some secure configuration - eg
    zookeeper.
    """
    with resources.path(package=webcheck, resource=CAFILE) as _cafile:
        # these are the default locations for the ssl files, stored in
        # package
        cafile = Path(_cafile)
        certfile = cafile.parent / CERTFILE
        keyfile = cafile.parent / KEYFILE

    context = create_ssl_context(
        cafile=cafile,
        certfile=certfile,
        keyfile=keyfile,
        password=None,
    )
    return context

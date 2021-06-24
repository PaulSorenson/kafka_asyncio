#!/bin/env python3

"""
webcheck CLI entry points

website checker

Notes:
- the configuration is packaged with the application -
  in production these would come from say zookeeper

kafka and postgresql instances in use:
https://console.aiven.io/project/metrak-749b/services

"""

import asyncio
import logging
import sys
from functools import partial
from importlib import resources
from pathlib import Path
from typing import List, Optional

import munch  # type: ignore
import typer
import yaml  # type: ignore

import webcheck
from webcheck.credentials import get_password
from webcheck.database import pg_connect_check, pg_create, pg_drop, pg_writer
from webcheck.kafka import get_kafka_ssl_context
from webcheck.page import PageCheck
from webcheck.webchecker import (
    DEFAULT_INTERVAL,
    console_writer,
    consumer_loop,
    producer_loop,
    round_trip_loop,
)

CONFIG_FILE = Path("webcheck.yaml")
KAFKA_SERVICE_URI = "kafka-1c4efd3-metrak-749b.aivencloud.com:18586"
TOPIC = "test_topic"


logging.basicConfig()
log = logging.getLogger()
app = typer.Typer()


def get_config(config_path: Optional[Path] = None) -> munch.Munch:
    """read config file

    In production this would come from say zookeeper or more manageable
    store.
    """
    config_file: Path = config_path if config_path is not None else CONFIG_FILE
    config = munch.Munch()
    with resources.open_text(package=webcheck, resource=config_file) as config_io:
        config.update(yaml.safe_load(config_io))
    mconfig = munch.munchify(config)
    mconfig.kafka.ssl = get_kafka_ssl_context()
    return mconfig


@app.callback()
def main(log_level: Optional[str] = "INFO"):
    lvl: str = log_level if log_level is not None else "INFO"
    log.setLevel(lvl)


@app.command()
def producer(config_path: Optional[Path] = None, interval: int = DEFAULT_INTERVAL):
    """start long running producer"""
    config = get_config(config_path=config_path)
    page_checks = [PageCheck(**site) for site in config.sites]
    rv = asyncio.run(
        producer_loop(
            uri=config.kafka.service_uri,
            topic=config.kafka.topic,
            ssl_context=config.kafka.ssl,
            interval=interval,
            collectors=[pc.check for pc in page_checks],
        )
    )
    sys.exit(rv)


@app.command()
def consumer(
    config_path: Optional[Path] = None,
    password: Optional[str] = None,
    console: bool = True,
):
    """start long running consumer"""
    config = get_config(config_path=config_path)
    # create pg writer
    pg_service_uri = config.postgresql.service_uri
    pg_username = config.postgresql.username
    pg_password = password or get_password(pg_username, "postgresql")
    uri = pg_service_uri.format(username=pg_username, password=pg_password)
    writers: List = [partial(pg_writer, uri)]
    if console:
        writers.append(console_writer)
    rv = asyncio.run(
        consumer_loop(
            uri=config.kafka.service_uri,
            topic=config.kafka.topic,
            ssl_context=config.kafka.ssl,
            writers=writers,
        )
    )
    sys.exit(rv)


@app.command()
def round_trip(
    config_path: Optional[Path] = None,
    password: Optional[str] = None,
    interval: int = DEFAULT_INTERVAL,
    console: bool = True,
):
    """start producer and consumer

    in a single process for demonstration purposes
    """
    config = get_config(config_path=config_path)
    page_checks = [PageCheck(**site) for site in config.sites]
    # create pg writer
    pg_service_uri = config.postgresql.service_uri
    pg_username = config.postgresql.username
    pg_password = password or get_password(pg_username, "postgresql")
    uri = pg_service_uri.format(username=pg_username, password=pg_password)
    writers: List = [partial(pg_writer, uri)]
    if console:
        writers.append(console_writer)
    rv = asyncio.run(
        round_trip_loop(
            uri=config.kafka.service_uri,
            topic=config.kafka.topic,
            ssl_context=config.kafka.ssl,
            collectors=[pc.check for pc in page_checks],
            writers=writers,
            interval=interval,
        )
    )
    sys.exit(rv)


@app.command()
def url_check(url: str = "https://example.com", regex: Optional[str] = None):
    """one shot web page check"""
    pg = PageCheck(url=url, regex=regex)
    text = asyncio.run(pg.check())
    print(text)


@app.command()
def pg_service(config_path: Optional[Path] = None, password: Optional[str] = None):
    """attempt connection to postgresql service

    The username and service_uri template are stored in the config file.
    Password sources are tried in order until a valid string is returned.
    - provided on command line
    - keyring is queried (command line equivalent `keyring get postgresql <username>`).
      The keyring package is included in pyproject.toml optional dependencies.
    - environment variable POSTGRES_PASSWORD
    - the user is prompted at the terminal
    """
    config = get_config(config_path=config_path)
    service_uri = config.postgresql.service_uri
    username = config.postgresql.username
    password = password or get_password(username, "postgresql")

    uri = service_uri.format(username=username, password=password)
    rv = asyncio.run(pg_connect_check(uri))
    sys.exit(rv)


@app.command()
def pg_table_create(config_path: Optional[Path] = None, password: Optional[str] = None):
    """create application tables

    Note the tables are lazily created by the service anyway so this is
    more for testing.
    """
    config = get_config(config_path=config_path)
    service_uri = config.postgresql.service_uri
    username = config.postgresql.username
    password = password or get_password(username, "postgresql")

    uri = service_uri.format(username=username, password=password)
    rv = asyncio.run(pg_create(uri))
    sys.exit(rv)


@app.command()
def pg_table_drop(
    password: str,
    config_path: Optional[Path] = None,
    prompt: bool = typer.Option(
        False, prompt="are you sure you want to permanently delete your tables?"
    ),
):
    """
    delete all the tables ...

    password must be supplied on command line.
    """

    config = get_config(config_path=config_path)
    service_uri = config.postgresql.service_uri
    username = config.postgresql.username
    if prompt:
        uri = service_uri.format(username=username, password=password)
        log.info(uri)
        rv = asyncio.run(pg_drop(uri))
        sys.exit(rv)


app()

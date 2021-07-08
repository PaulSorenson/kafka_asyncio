#!/bin/env python3

"""
data persistence for webcheck application

Also has some high level functions for CLI utilities.
"""

import logging

import asyncpg  # type: ignore

# from webcheck.schema import PageMetrics
from webcheck.webchecker import ConsumerPayload

logging.basicConfig()
log = logging.getLogger()

DEFAULT_TIMEOUT = 30
# get this from yaml with place holders for username and password
PG_SERVICE_URI = "postgres://{}:{}@{pg_host}:18584/defaultdb?sslmode=require"
TABLE_NAME = "webcheck"
TIME_FIELD = "time"

# @todo: compose SQL from PageMetrics schema
# for now we hand code it taking care the
# field ordering is the same as PageMetrics

SQL_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    {TIME_FIELD} TIMESTAMPTZ NOT NULL,
    url VARCHAR NOT NULL,
    status SMALLINT,
    response_time REAL,
    regex_matched bool,
    PRIMARY KEY({TIME_FIELD}, url)
);
"""

# since the incoming time is a unix timestamp it is implicitly UTC it
# transformed to UTC TIMESTAMPTZ here
SQL_INSERT = f"""
INSERT INTO {TABLE_NAME} (
    {TIME_FIELD},
    url,
    status,
    response_time,
    regex_matched
) VALUES (
    to_timestamp($1), $2, $3, $4, $5
)
"""

SQL_DROP = f"DROP TABLE IF EXISTS {TABLE_NAME};"


async def pg_writer(service_uri: str, payload: ConsumerPayload) -> int:
    """write page metrics to table

    Args:
        service_uri: pg dsn
        payload: this is the form the data comes to the writer in. Ideally
            it would be a PageMetrics instances but we would need to serialize
            the dataclass symmetrically over the bytes messaging content
            of kafka. We have cheated here by deliberately encode/decode
            as a Tuple and as long as the fields line up between
            PageMetrics -> ConsumerPayload -> insert_sql we are good.

    This is a one-shot writer, connections are created for each
    write. For higher throughput applications re-using the connection
    could be a better idea.
    """
    try:
        connection: asyncpg.Connection = await asyncpg.connect(
            service_uri, timeout=DEFAULT_TIMEOUT
        )
        log.debug("writer: successful connection to postgresql service")
        sql = SQL_INSERT
        log.debug(sql)
        await connection.execute(
            sql,
            *payload,
            timeout=DEFAULT_TIMEOUT,
        )
        log.info(f"pg_writer: written {payload}")
        await connection.close(timeout=DEFAULT_TIMEOUT)
    except asyncpg.exceptions.UniqueViolationError:
        log.warning("unique key error @todo tidy up kafka consumer")
    except Exception:
        log.error("failure: postgresql connect - the pg-table-create command might help")
        # if we get insert errors lets just bail out.
        raise
    return 0


async def pg_connect_check(service_uri: str) -> bool:
    """go/nogo check of postgresql connection

    Args:
        service_uri: dss passed to postgres client connect.
    """
    try:
        connection: asyncpg.Connection = await asyncpg.connect(
            service_uri, timeout=DEFAULT_TIMEOUT
        )
        log.info("successful connection to postgresql service")
        await connection.close()
        return True
    except Exception as ex:
        log.error(f"failure: postgresql connect {ex}")
    return False


async def pg_drop(service_uri: str) -> bool:
    """drop the webcheck pg tables"""
    connection: asyncpg.Connection = await asyncpg.connect(
        service_uri, timeout=DEFAULT_TIMEOUT
    )
    log.info(SQL_DROP)
    rv = await connection.execute(SQL_DROP, timeout=DEFAULT_TIMEOUT)
    await connection.close(timeout=DEFAULT_TIMEOUT)
    return rv


async def pg_create(service_uri: str) -> bool:
    """create the webcheck pg tables"""
    connection: asyncpg.Connection = await asyncpg.connect(
        service_uri, ssl="require", timeout=DEFAULT_TIMEOUT
    )
    log.info(SQL_CREATE)
    rv = await connection.execute(SQL_CREATE, timeout=DEFAULT_TIMEOUT)
    await connection.close(timeout=DEFAULT_TIMEOUT)
    return rv

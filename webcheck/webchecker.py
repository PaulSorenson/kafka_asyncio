#!/bin/env python3

"""
webchecker contains the major operational framework
co-ordinating asyncio tasks end to end for the application

- producer_loop: entry point for collecting and publishing data
- consumer_loop: entry point for consuming and persisting data

These marshal internal tasks to co-ordinate the interactions with
kafka and the outside world (eg web pages)

At least one of each is required for a functional system. Since messages
in kafka are durable and the semantics of pub/sub - they don't have to
be started at the same time.

The **components that specialize the system are collectors and writers**. In our case
we have a PageCheck collector. The key writer is a postgres writer but there is also
a console_writer provided for printing the received data to stdout. This is enabled
by default and can be disabled with --no-console argument

Separation of concerns and "one" purpose has driven the design of the components is also
heavily influences by asyncio semantics.

The lines where asyncio.gather() is invoked are the key to understanding the task
concurrencies.

The kafka group_id is hardwired here.
"""

import asyncio
import json
import logging
import time
from dataclasses import astuple
from ssl import SSLContext
from typing import Awaitable, Callable, List, Tuple

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore

from webcheck.page import PageMetrics

# signal the consumer to end gracefully
EOT = b"0x04"
DEFAULT_INTERVAL = 15
DEFAULT_GROUP_ID = "webchecker"

# Use this for type pushed in internal queue at the consumer.
# at the producer end we can send page_metrics as is but since
# we have to encode that as bytes over kafka this is not
# symetrical for
ConsumerPayload = Tuple

log = logging.getLogger()


async def scheduler(
    queue: asyncio.Queue[PageMetrics],
    collector: Callable[[], Awaitable[PageMetrics]],
    interval: int = DEFAULT_INTERVAL,
) -> int:
    """long running collection loop for a single collector

    Each interval seconds, result of collector() is pushed to the queue.
    Spin up one of these for each page to be checked.

    This is what drives the whole system.

    Args:
        queue: python data is pushed here towards encoder
        collector: takes no args, returns application specific data.
    """
    i = 0
    while True:
        # this is a very rudimentary scheduling scheme ;)
        delta = interval - time.time() % interval
        log.info("next event in %i seconds", delta)
        # sleep till next check time
        await asyncio.sleep(delta)
        payload = await collector()
        log.info("loop %i %s", i, payload)
        await queue.put(payload)
        i += 1
    return 0


async def encoder(
    queue: asyncio.Queue[PageMetrics], producer: AIOKafkaProducer, topic: str
) -> int:
    """
    Waits on queue for incoming python objects, encodes them and publishes.

    Cheating here a little by encoding page metrics as a tuple.
    In real life we would probably use thrift or proto buf
    to serialize. pickle would be another option for perfect symmetry on
    producer consumer ends but would lock us into Python.

    astuple() is not a random accident - it anticipates being passed
    to a postgres execute query but in a more generic world we could not
    make this assumption.

    Args:
        queue: source for application objects - PageMetrics in this case.
        producer: kafka producer client
        topic: kafka topic
    """
    while True:
        payload: PageMetrics = await queue.get()
        bpayload = json.dumps(astuple(payload)).encode("utf8")
        await producer.send_and_wait(topic, bpayload)


async def producer_loop(
    uri: str,
    topic: str,
    ssl_context: SSLContext,
    collectors: List[Callable[[], Awaitable[PageMetrics]]],
    interval: int = DEFAULT_INTERVAL,
) -> int:
    """collect page metrics and publish results to kafka

    This is one of the two key entry points for the application (user
    interaction notwithstanding).

    Abstractly, it schedules each collector and then marshals the output onto
    a kafka producer client.

    It coordinates:

    - collector: responsible for generating the "raw" data for the system, it determines
    what published to the kafka topic.

    One or more of these is passed to the producer_loop by the caller. They collect
    data and return (one-shot). If you want to maintain state between invocations
    consider designing a class that has a method that meets the requirements of
    a collector.

    Collectors take no arguments - so either use a method from a class or make use
    of functool.partial to curry parameters (in our case, urls and regexes)

    - scheduler: the producer_loop wraps each collector in a scheduler which runs
    the collector at regular intervals and pushes python objects onto an asyncio.Queue.

    - encoder: listens on collector queue, encodes the collector objects and publishes
    them to the kafka publisher client.

    Args:
        uri: kafka service uri
        topic: kafka topic
        ssl_context: instance of ssl.SSLContext
        collectors: list of colletor components. This is what "makes" the application
            and here we are using PageCheck instances. Each collector is awaitable and
            returns application data as a python object.
    """
    log.info("producer starting")
    if len(collectors) < 1:
        raise ValueError("At least one collector must be passed to producer_loop")
    queue: asyncio.Queue[PageMetrics] = asyncio.Queue()
    collector_coros = [
        scheduler(queue=queue, collector=c, interval=interval) for c in collectors
    ]
    async with AIOKafkaProducer(
        bootstrap_servers=uri,
        security_protocol="SSL",
        ssl_context=ssl_context,
    ) as producer:
        # kick off one encoder and n schedulers
        rv = await asyncio.gather(encoder(queue, producer, topic), *collector_coros)
    log.info("producer exiting %s", rv)
    return 0


async def decoder(
    queue: asyncio.Queue[ConsumerPayload],
    consumer: AIOKafkaConsumer,
) -> int:
    """dispatches messages from subscribed topic and pushes them to writers.

    Analagous to encoder on produce side although not a perfect mirror image
    due to the basic encoding used.

    Args:
        queue: comms between decoder and writers
        consumer: kafka consumer client
    """
    log.info("decoder: starting")
    try:
        async for msg in consumer:
            if msg.value == EOT:
                log.info("decoder: EOT received")
                break
            log.info(
                "consumed: %s %s %s %s %s %s",
                msg.topic,
                msg.partition,
                msg.offset,
                msg.key,
                msg.value,
                msg.timestamp,
            )
            bpayload: bytes = msg.value
            payload: ConsumerPayload = json.loads(bpayload)
            await queue.put(payload)
    except Exception:
        log.exception("decoder: exception")
    log.info("decoder: exiting")
    return 0


async def writer_wrapper(
    queue: asyncio.Queue[ConsumerPayload],
    writers: List[Callable[[ConsumerPayload], Awaitable[int]]],
) -> int:
    """waits on decoded data and invokes each writer

    Args:
        queue: gets data pushed by decoder
        writers: each writer gets called with a the data consumed
            from the queue. Note these are not copied so writers
            should not mutate them directly.
    """
    while True:
        payload = await queue.get()
        log.info("writer_wrapper[%s]: %s", len(writers), payload)
        await asyncio.gather(*[writer(payload) for writer in writers])


async def console_writer(payload: ConsumerPayload):
    """writes payload to console

    An example of a minimalist writer that can be plugged into
    the consumer loop.
    """
    print(f"console writer: {payload}")


async def consumer_loop(
    uri: str,
    topic: str,
    ssl_context: SSLContext,
    writers: List[Callable[[ConsumerPayload], Awaitable[int]]],
) -> int:
    """consume web data from kafka topic and distributes it to writers

    Args:
        uri: kafka service uri
        topic: kafka topic
        ssl_context: instance of ssl.SSLContext
        writers: means for egressing data from application.
    """
    log.info("consumer: starting")
    if len(writers) < 1:
        raise ValueError("there must be at least one writer passed to consumer_loop.")
    queue: asyncio.Queue[ConsumerPayload] = asyncio.Queue()
    async with AIOKafkaConsumer(
        topic,
        bootstrap_servers=uri,
        security_protocol="SSL",
        ssl_context=ssl_context,
        group_id=DEFAULT_GROUP_ID,
    ) as consumer:
        await asyncio.gather(
            decoder(queue, consumer), writer_wrapper(queue=queue, writers=writers)
        )
        log.info("consumer: exiting")
    return 0


async def round_trip_loop(
    uri: str,
    topic: str,
    ssl_context: SSLContext,
    collectors: List[Callable[[], Awaitable[PageMetrics]]],
    writers: List[Callable[[ConsumerPayload], Awaitable[int]]],
    interval: int = DEFAULT_INTERVAL,
) -> int:
    """fire up producer and consumer in the same process"""
    result = await asyncio.gather(
        producer_loop(
            uri=uri,
            topic=topic,
            ssl_context=ssl_context,
            interval=interval,
            collectors=collectors,
        ),
        consumer_loop(uri=uri, topic=topic, ssl_context=ssl_context, writers=writers),
    )
    log.info(result)
    return 0

import asyncio
from typing import List
from aiokafka import AIOKafkaProducer


async def check_loop():
    for i in range(10):
        print("hello world")
        await asyncio.sleep(1)


def main():
    result = asyncio.run(check_loop())

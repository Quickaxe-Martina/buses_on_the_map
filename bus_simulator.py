import argparse
import itertools
import json
import logging
import random
from functools import wraps
from logging import config as logging_config
from pathlib import Path

import trio
from trio import MemoryReceiveChannel, MemorySendChannel
from trio_websocket import ConnectionClosed, HandshakeError, open_websocket_url
from wsproto.utilities import LocalProtocolError

from logging_config import LOGGING

FOLDER = "./routes"
logging_config.dictConfig(LOGGING)


def generate_bus_id(emulator_id, route_id, bus_index):
    return f"{emulator_id}-{route_id}-{bus_index}"


def relaunch_on_disconnect(async_function):
    @wraps(async_function)
    async def wrapped(*args, **kwargs):
        while True:
            try:
                await async_function(*args, **kwargs)
            except (
                ConnectionClosed,
                HandshakeError,
                LocalProtocolError,
            ):
                logging.error("reconnect socket")
                await trio.sleep(3)

    return wrapped


@relaunch_on_disconnect
async def send_updates(receive_channel: MemoryReceiveChannel, server_url: str):
    async with open_websocket_url(server_url) as ws:
        async with receive_channel:
            async for value in receive_channel:
                try:
                    await ws.send_message(
                        json.dumps(
                            value,
                            ensure_ascii=False,
                        )
                    )
                except ConnectionClosed:
                    logging.error("Connection closed")
                    break


async def fake_bus(
    data: dict, bus_id: str, send_channel: MemorySendChannel, refresh_timeout: float
):
    cycle_coords = itertools.cycle(data["coordinates"])
    sliced_coords = itertools.islice(
        cycle_coords, random.randint(0, len(data["coordinates"])), None
    )
    async with send_channel:
        for coord in sliced_coords:
            await send_channel.send(
                {
                    "busId": bus_id,
                    "lat": coord[0],
                    "lng": coord[1],
                    "route": data["name"],
                }
            )
            await trio.sleep(refresh_timeout)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server",
        help="адрес сервера",
        default="ws://127.0.0.1:80/bus_ws/",
    )
    parser.add_argument(
        "--routes_number",
        type=int,
        default=10,
        choices=range(1, 1000),
        help="количество маршрутов",
    )
    parser.add_argument(
        "--buses_per_route",
        type=int,
        default=5,
        choices=range(1, 100),
        help="количество автобусов на каждом маршруте",
    )
    parser.add_argument(
        "--websockets_number",
        type=int,
        default=10,
        choices=range(1, 50),
        help="количество открытых веб-сокетов",
    )
    parser.add_argument(
        "--emulator_id",
        default="1",
        help="префикс к busId на случай запуска нескольких экземпляров имитатора",
    )
    parser.add_argument(
        "--refresh_timeout",
        type=float,
        default=1.0,
        help="задержка в обновлении координат сервера",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        type=int,
        choices=range(0, 51, 10),
        default=20,
        help="настройка логирования",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    send_channels: list[MemorySendChannel] = []
    async with trio.open_nursery() as nursery:
        for _ in range(args.websockets_number):
            send_channel, receive_channel = trio.open_memory_channel(0)
            send_channels.append(send_channel)
            nursery.start_soon(send_updates, receive_channel, args.server)
        r_count = 0
        for filepath in Path(FOLDER).glob("*.json"):
            if r_count > args.routes_number:
                break
            with open(filepath, "r", encoding="utf8") as f:
                data = json.load(f)
            for i in range(args.buses_per_route):
                nursery.start_soon(
                    fake_bus,
                    data,
                    generate_bus_id(
                        route_id=data["name"],
                        bus_index=i,
                        emulator_id=args.emulator_id,
                    ),
                    random.choice(send_channels),
                    args.refresh_timeout,
                )
            r_count += 1


if __name__ == "__main__":
    trio.run(main)

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from json import JSONDecodeError
from logging import config as logging_config

import trio
from trio_websocket import (
    ConnectionClosed,
    WebSocketConnection,
    WebSocketRequest,
    serve_websocket,
)

from logging_config import LOGGING

logging_config.dictConfig(LOGGING)


@dataclass
class Bus:
    busId: str
    lat: float
    lng: float
    route: str


@dataclass
class WindowBounds:
    west_lng: float = 0.0
    east_lng: float = 0.0
    south_lat: float = 0.0
    north_lat: float = 0.0

    def update(self, new: dict):
        for key, value in new.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def is_inside(self, bus: Bus):
        return (
            self.south_lat < bus.lat < self.north_lat
            and self.west_lng < bus.lng < self.east_lng
        )


BUSES: dict[str, Bus] = {}
DELAY_BROWSER = 1


async def talk_to_browser(ws: WebSocketConnection, win_bounds: WindowBounds):
    while True:
        try:
            buses = [asdict(bus) for bus in BUSES.values() if win_bounds.is_inside(bus)]
            logging.info(f"talk_to_browser: {len(buses)=}")
            await ws.send_message(
                json.dumps(
                    {
                        "msgType": "Buses",
                        "buses": buses,
                    }
                )
            )
        except ConnectionClosed:
            break
        await trio.sleep(DELAY_BROWSER)


async def listen_browser(ws: WebSocketConnection, win_bounds: WindowBounds):
    while True:
        try:
            msg = await ws.get_message()
            try:
                win_bounds.update(json.loads(msg)["data"])
            except (TypeError, JSONDecodeError, KeyError):
                await ws.send_message(
                    json.dumps({"errors": "Requires valid JSON", "msgType": "Errors"})
                )
                continue
            logging.info(f"{win_bounds=}")
        except ConnectionClosed:
            break


async def client_server(request: WebSocketRequest):
    ws = await request.accept()
    win_bounds = WindowBounds()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(talk_to_browser, ws, win_bounds)
        nursery.start_soon(listen_browser, ws, win_bounds)


async def bus_server(request: WebSocketRequest):
    ws = await request.accept()
    while True:
        try:
            message = await ws.get_message()
            try:
                bus = Bus(**json.loads(message))
            except (TypeError, JSONDecodeError, KeyError):
                await ws.send_message(
                    json.dumps({"errors": "Requires valid JSON", "msgType": "Errors"})
                )
                continue
            BUSES[bus.busId] = bus
        except ConnectionClosed:
            break


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bus_port",
        help="порт для имитатора автобусов",
        type=int,
        default=8080,
    )
    parser.add_argument(
        "--browser_port",
        type=int,
        default=8000,
        help="порт для браузера",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    async with trio.open_nursery() as nursery:
        nursery.start_soon(
            serve_websocket, client_server, "127.0.0.1", args.browser_port, None
        )
        nursery.start_soon(
            serve_websocket, bus_server, "127.0.0.1", args.bus_port, None
        )


if __name__ == "__main__":
    trio.run(main)

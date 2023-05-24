import json

import trio
from trio_websocket import open_websocket_url


async def send_harmful_messages(server_url):
    async with open_websocket_url(server_url) as ws:
        for msg in ("", "{}", "null"):
            await ws.send_message(msg)
            response = json.loads(await ws.get_message())
            print(f"{response=}")
            print(f'{response["msgType"] == "Errors"=}')


async def main():
    async with trio.open_nursery() as nursery:
        nursery.start_soon(send_harmful_messages, "ws://127.0.0.1:8000/ws")


if __name__ == "__main__":
    trio.run(main)

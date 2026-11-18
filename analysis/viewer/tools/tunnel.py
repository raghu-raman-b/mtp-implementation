#!/usr/bin/env python3
"""A TCP proxy that behaves like an SSH port forward over a slow link (ssh -L is not available here: no key login to
localhost, no root for tc/netem).

    python tunnel.py LISTEN_PORT TARGET_PORT [--rtt-ms 200] [--mbit 10] [--window-kb 2048]

Like ssh -L, every browser connection shares ONE link: one bandwidth budget per direction (a token bucket shared by
all connections), a one-way delay of rtt/2 on every chunk, and a per-connection window (SSH's channel window) so a
connection the browser stopped reading cannot buffer unbounded data in the link.
Counts bytes per direction and prints a line per connection when it closes.
"""
import argparse
import asyncio
import time


class Link:
    def __init__(self, mbit: float, delay: float):
        self.rate = mbit * 1e6 / 8          # bytes per second
        self.delay = delay
        self.free_at = 0.0                  # when the link is free to start sending the next chunk
        self.bytes = 0

    def schedule(self, n: int) -> float:
        now = time.monotonic()
        start = max(now, self.free_at)
        self.free_at = start + n / self.rate
        self.bytes += n
        return self.free_at + self.delay      # when the last byte of this chunk arrives on the other side


async def pump(reader, writer, link: Link, window: int, tag: str, stats: dict):
    q: asyncio.Queue = asyncio.Queue(maxsize=max(1, window // 16384))

    async def deliver():
        while True:
            item = await q.get()
            if item is None:
                break
            at, data = item
            d = at - time.monotonic()
            if d > 0:
                await asyncio.sleep(d)
            try:
                writer.write(data)
                await writer.drain()
            except (ConnectionError, OSError):
                break
        try:
            writer.close()
        except Exception:
            pass

    task = asyncio.create_task(deliver())
    try:
        while True:
            data = await reader.read(16384)
            if not data:
                break
            stats[tag] += len(data)
            await q.put((link.schedule(len(data)), data))
    except (ConnectionError, OSError):
        pass
    await q.put(None)
    await task


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("listen", type=int)
    ap.add_argument("target", type=int)
    ap.add_argument("--rtt-ms", type=float, default=200)
    ap.add_argument("--mbit", type=float, default=10)
    ap.add_argument("--up-mbit", type=float, default=None)
    ap.add_argument("--window-kb", type=int, default=2048)
    a = ap.parse_args()
    down = Link(a.mbit, a.rtt_ms / 2000)
    up = Link(a.up_mbit or a.mbit, a.rtt_ms / 2000)
    n = 0

    async def handle(cr, cw):
        nonlocal n
        n += 1
        stats = {"up": 0, "down": 0}
        # the connection itself costs a round trip through the link (as a new SSH channel does)
        await asyncio.sleep(a.rtt_ms / 1000)
        try:
            sr, sw = await asyncio.open_connection("127.0.0.1", a.target)
        except OSError:
            cw.close()
            return
        t0 = time.monotonic()
        await asyncio.gather(pump(cr, sw, up, a.window_kb * 1024, "up", stats),
                             pump(sr, cw, down, a.window_kb * 1024, "down", stats))
        print(f"conn {n}: down {stats['down']/1024:.0f} kB up {stats['up']/1024:.1f} kB in {time.monotonic()-t0:.1f} s",
              flush=True)

    srv = await asyncio.start_server(handle, "127.0.0.1", a.listen)
    print(f"tunnel :{a.listen} -> :{a.target}  rtt {a.rtt_ms} ms, {a.mbit} Mbit/s, window {a.window_kb} kB", flush=True)
    async with srv:
        await srv.serve_forever()


asyncio.run(main())

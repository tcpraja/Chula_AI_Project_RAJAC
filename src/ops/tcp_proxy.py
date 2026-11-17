"""Tiny TCP forwarder used by docker-compose: publishes the dashboard on 127.0.0.1 while the app container itself sits on an internal network
with no outbound route. It forwards bytes to ONE fixed target and does nothing else. Run: python -m src.ops.tcp_proxy --listen 0.0.0.0:8501 --target app:8501"""
import argparse
import asyncio


async def _pipe(r, w):
    try:
        while data := await r.read(65536):
            w.write(data)
            await w.drain()
    finally:
        w.close()


async def serve(listen, target):
    lh, lp = listen.rsplit(":", 1)
    th, tp = target.rsplit(":", 1)

    async def handle(cr, cw):
        try:
            ur, uw = await asyncio.open_connection(th, int(tp))
        except OSError:
            cw.close()
            return
        await asyncio.gather(_pipe(cr, uw), _pipe(ur, cw), return_exceptions=True)

    server = await asyncio.start_server(handle, lh, int(lp))
    async with server:
        await server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--listen", required=True)
    ap.add_argument("--target", required=True)
    a = ap.parse_args()
    asyncio.run(serve(a.listen, a.target))


if __name__ == "__main__":
    main()

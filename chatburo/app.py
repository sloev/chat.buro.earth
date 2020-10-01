import trustpilot_json_logging

logging = trustpilot_json_logging.setup_logging()

from sanic import Sanic
from sanic.response import json, text, stream, html
import time
import io
import asyncio
from collections import defaultdict, deque
import asyncio_redis
from chatburo import settings, text_render

app = Sanic("hello_example")


@app.listener("before_server_start")
async def setup_db(app, loop):
    # Create Redis connection
    app.redis_connection = await asyncio_redis.Pool.create(
        host=settings.REDIS_HOST, port=6379, poolsize=10
    )


@app.listener("before_server_stop")
async def notify_server_stopping(app, loop):
    await app.redis_connection.close()


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


@app.route("/<chat_id>", methods=["POST"])
async def index(request, chat_id):
    try:
        username = request.form.get("username")
        message = request.form.get("message")
        if not username or len(username) > 15 or not is_ascii(username):
            return text("username wrong format", 400)
        if not message or len(message) > 140 or not is_ascii(message):
            return text("message wrong format", 400)

        message = f"{username.rjust(16)} > {message}"

        await request.app.redis_connection.set(
            f"{chat_id}.{int(time.time()*1000.0)}", message, expire=60
        )

        await request.app.redis_connection.publish(chat_id, message)
        return html(
            """<body onload="window.open('', '_self', ''); window.close();"><h1>...loading</h1></body>"""
        )
    except asyncio_redis.Error as e:
        logging.exception("Published failed")
    # brug https://pypi.org/project/aiopubsub/
    # sætter eller læser en cookie indeholdende uuid for client
    # tager input og putter ind i kø
    # processor tråd tager ud af kø og gemmer i under_construction
    # processor går igennem under construction en gang imellem for at groome gamle ufærddigjorte beskeder væk
    # processor putter hele binære (inkl frame) beskeder i outgoing når der er færdiggjorte
    return text("error")


async def topic_messages(redis_connection, chat_id):
    cursor = await redis_connection.scan(match=f"{chat_id}.*")
    while True:
        key = await cursor.fetchone()
        if key is None:
            break
        value = await redis_connection.get(key)
        if value:
            yield value

    subscriber = await redis_connection.start_subscribe()
    await subscriber.subscribe([chat_id])
    try:
        # Inside a while loop, wait for incoming events.
        while True:
            need_sleep = False
            while need_sleep is False:
                try:
                    message = subscriber._messages_queue.get_nowait()
                    yield message.value
                except asyncio.QueueEmpty:
                    need_sleep = True
                    yield None
            await asyncio.sleep(0.5)
    except:
        logging.exception("err")
    finally:
        logging.warning("exiting loop")
        await subscriber.unsubscribe([chat_id])


@app.route("/<chat_id>/image.mjpg")
async def index(request, chat_id):
    async def streaming_fn(response):
        last_10_messages = deque(maxlen=10)
        async for message in topic_messages(request.app.redis_connection, chat_id):
            if message is not None:
                last_10_messages.append(message)
                logging.warning(f"got message: {message}")
            frame = await text_render.render(last_10_messages)
            await response.write(
                b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )
        logging.info("ending stream")

    return stream(
        streaming_fn,
        headers={
            "Content-Type": "multipart/x-mixed-replace; boundary=--frame",
            "Connection": "close",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        },
    )


def run():
    app.run(host="0.0.0.0", port=8000)


if __name__ == "__main__":
    run()

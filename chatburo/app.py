import trustpilot_json_logging

logging = trustpilot_json_logging.setup_logging()

from sanic import Sanic
from sanic.response import json, text, stream, html
import time
import io
import asyncio
from collections import defaultdict, deque
import string
from chatburo import settings, rendering, static, utils, db
from urllib.parse import urlparse

app = Sanic("hello_example")
for css_filename, css_path in static.css_files.items():
    app.static(f"/static/{css_filename}", css_path, name=css_filename)

EXAMPLE_CHAT = static.templates["chatform_html"].substitute(
    chatburo_css_url=f"/static/{css_filename}",
    chatburo_width_px="320px",
    chatburo_height_px="400px",
    chatburo_img_url=f"/{settings.EXAMPLE_CHAT_HASH}/image.mjpg",
    chatburo_post_url=f"/{settings.EXAMPLE_CHAT_HASH}",
    chatburo_target_name=settings.CHATBURO_TARGET_NAME,
)


def is_ascii(s):
    return all(ord(c) < 128 for c in s)


@app.listener("before_server_start")
async def setup_db(app, loop):
    app.db = db.SqliteBackedPubSub()
    app.rendering_pool = await rendering.AsyncTextWorkerPool().setup()
    await app.db.connect(settings.SQLITE_DB_PATH)


@app.listener("before_server_stop")
async def notify_server_stopping(app, loop):
    await app.db.close()
    app.rendering_pool.close()


@app.route("/create", methods=["POST"])
async def index(request):
    width = request.form.get("width")
    height = request.form.get("height")
    origin = request.form.get("origin")
    json_web_token = utils.encode(origin)

    new_form = static.templates["chatform_html"].substitute(
        chatburo_css_url=f"/static/{css_filename}",
        chatburo_width_px=f"{width}px",
        chatburo_height_px=f"{height}px",
        chatburo_img_url=f"/{json_web_token}/image.mjpg?width={width}&height={height}",
        chatburo_post_url=f"/{json_web_token}",
        chatburo_target_name=settings.CHATBURO_TARGET_NAME,
    )
    return html(
        static.templates["index_html"].substitute(
            chatburo_new_form_url=f"/create#snippet-form",
            chatburo_created_form_display="block",
            chatburo_created_form=new_form,
            chatburo_example_chat=EXAMPLE_CHAT,
            chatburo_created_clear_display="initial",
        )
    )


@app.route("/", methods=["GET"])
async def index(request):
    return html(
        static.templates["index_html"].substitute(
            chatburo_new_form_url=f"/create#snippet-form",
            chatburo_created_form_display="none",
            chatburo_created_form="",
            chatburo_example_chat=EXAMPLE_CHAT,
            chatburo_created_clear_display="none",
        )
    )


@app.route("/<chat_id>", methods=["POST"])
async def index(request, chat_id):
    request_origin = request.headers.get("origin")
    origin = utils.decode(chat_id)
    if origin:
        if urlparse(request_origin).netloc != origin:
            return text("this domain is not authorized to post to this chat id", 401)

    username = request.form.get("username")
    message = request.form.get("message")
    if (
        not username
        or len(username) > 15
        or not is_ascii(username)
        or not message
        or len(message) > 140
        or not is_ascii(message)
    ):
        return text(
            "wrong format: {username: {max_len:15, encoding:ascii}, message: {max_len:140, encoding:ascii} }",
            400,
        )

    await request.app.db.publish(chat_id, username, message)
    return html(
        """<body onload="window.open('', '_self', ''); window.close();"><h1>...loading</h1></body>"""
    )


@app.route("/<chat_id>/image.mjpg")
async def index(request, chat_id):
    width = int(request.args.get("width") or 320)
    height = int(request.args.get("height") or 400)
    if width < 50 or width > 600 or height < 50 or height > 600:
        return text("dimensions need to be 50px to 600px", 400)

    async def streaming_fn(response):
        last_10_messages = deque(maxlen=int(height / 16))
        frame = None
        async for visitors, message in request.app.db.subscribe(chat_id):
            if message is not None:
                last_10_messages.append(message)
            frame = await request.app.rendering_pool.messages_to_jpeg(
                last_10_messages, width=width, height=height, visitors=visitors
            )

            await response.write(
                b"--frame\r\n" b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            )

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
    app.run(host="0.0.0.0", port=8000, access_log=False)


if __name__ == "__main__":
    run()

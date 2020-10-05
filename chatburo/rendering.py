#!/usr/bin/env python
# coding: utf-8

# Copyright 2011 Álvaro Justen [alvarojusten at gmail dot com]
# License: GPL <http://www.gnu.org/copyleft/gpl.html>
import sys
import json
import asyncio
import logging
import os

if __name__ == "__main__":
    logging.basicConfig(filename="out.log", filemode="a")


from PIL import Image, ImageDraw, ImageFont

FONT_CACHE = {}


def load_font(filename, size):
    key = f"{filename}_{size}"
    font = FONT_CACHE.get(key)
    if font is None:
        current_dir = os.path.dirname(__file__)
        font = ImageFont.truetype(f"{current_dir}/{filename}", size)
        FONT_CACHE[key] = font
    return font


class ImageText(object):
    def __init__(
        self,
        filename=None,
        new_img_size=None,
        mode="RGB",
        background=(0, 0, 0),
        encoding="utf8",
    ):
        if filename is not None:
            self.image = Image.open(filename)
            self.size = self.image.size
        elif new_img_size is not None:
            self.size = tuple(new_img_size)
            self.image = Image.new(mode, self.size, color=tuple(background))
        else:
            raise ValueError("needs filename or new_img_size")

        self.draw = ImageDraw.Draw(self.image)
        self.encoding = encoding

    def save(
        self, filename_or_buffer, format, quality=80, optimize=True, progressive=False
    ):
        self.image.save(
            filename_or_buffer,
            format=format,
            quality=quality,
            optimize=optimize,
            progressive=progressive,
        )

    def get_font_size(self, text, font, max_width=None, max_height=None):
        if max_width is None and max_height is None:
            raise ValueError("You need to pass max_width or max_height")
        font_size = 1
        text_size = self.get_text_size(font, font_size, text)
        if (max_width is not None and text_size[0] > max_width) or (
            max_height is not None and text_size[1] > max_height
        ):
            raise ValueError("Text can't be filled in only (%dpx, %dpx)" % text_size)
        while True:
            if (max_width is not None and text_size[0] >= max_width) or (
                max_height is not None and text_size[1] >= max_height
            ):
                return font_size - 1
            font_size += 1
            text_size = self.get_text_size(font, font_size, text)

    def write_text(
        self, xy, text, font_filename="COMIC.TTF", font_size=11, color=(255, 255, 255)
    ):
        x, y = xy
        color = tuple(color)

        font = load_font(font_filename, font_size)
        self.draw.text((x, y), text, font=font, fill=color)

    def get_text_size(self, text, font_filename="COMIC.TTF", font_size=12):
        font = load_font(font_filename, font_size)
        return font.getsize(text)

    def create_multiline_args(
        self, text, box_width, font_filename="COMIC.TTF", font_size=11
    ):
        word_lines = []
        line = []
        words = text.split()
        for word in words:
            new_line = " ".join(line + [word])
            size = self.get_text_size(
                new_line, font_filename=font_filename, font_size=font_size
            )
            text_height = size[1]
            if size[0] <= box_width:
                line.append(word)
            elif len(line) < 1 and size[0] > box_width:
                while word:
                    chars = int(box_width / (font_size / 2))
                    word_lines.append([word[:chars]])
                    word = word[chars:]

            else:
                word_lines.append(line)
                line = [word]
        if line:
            word_lines.append(line)
        lines = []
        height = 0
        for word_line in word_lines:
            if word_line:
                lines.append(" ".join(word_line))
                height += text_height
        return (lines, height, text_height)

    def render_text_box(
        self,
        lines,
        xy,
        text_height,
        font_filename="COMIC.TTF",
        font_size=11,
        color=(255, 255, 255),
    ):
        color = tuple(color)
        x, y = xy
        height = y
        for index, line in enumerate(lines):
            self.write_text((x, height), line, font_filename, font_size, color)
            height += text_height


def process(job_args, output):
    width = job_args["width"]
    height = job_args["height"]
    vertical_space = 15
    visitors = job_args.get("visitors", None) or 0

    quality = job_args.get("quality", 100)
    output_format = job_args.get("format", "JPEG")

    background_color = job_args.get("background_color", [28, 28, 28])
    img = ImageText(new_img_size=(width, height), background=background_color)

    img.write_text(
        [0, height - (vertical_space * 3)],
        f" _ " * 200,
        font_size=14,
        color=(140, 240, 255),
    )
    img.write_text(
        [10, height - (int(vertical_space * 1.6))],
        f"visitors: {visitors}",
        font_size=14,
        color=(140, 255, 178),
    )

    y = height - vertical_space * 4
    for instruction in job_args["instructions"]:
        author = f"[ {instruction['author']} ]"
        x_margin = img.get_text_size(author, font_size=14)[0] + 20
        box_width = width - (x_margin + vertical_space * 2)

        message = instruction["message"]
        lines, box_height, text_height = img.create_multiline_args(
            message, box_width, font_size=14
        )
        y -= box_height - vertical_space
        logging.warning(f"height: {box_height}, vertical_space:{vertical_space}")
        img.render_text_box(
            lines, [x_margin, y], text_height, font_size=14, color=(140, 240, 255)
        )
        img.write_text([10, y], author, font_size=14, color=(140, 255, 178))

        y -= vertical_space * 2

    img.save(output, format=output_format, quality=100)


def main():
    logging.warning("started process thread")
    output = sys.stdout.buffer

    while True:
        try:
            job_args_line = sys.stdin.readline()
            logging.warning(f"got from stdout:{job_args_line}")
            if job_args_line:
                logging.warning("got line" + job_args_line)
                job_args = json.loads(job_args_line)
                process(job_args, sys.stdout.buffer)
                logging.warning("wrote to stdout")

        except KeyboardInterrupt:
            break
        except:
            logging.exception("err")
            raise
    logging.warning("exited")


class AsyncTextWorkerPool:
    async def setup(self, workers=4):
        self.n = workers
        cmd = ["python", __file__]
        print(cmd)
        self.workers = await asyncio.gather(
            *[
                asyncio.create_subprocess_shell(
                    " ".join(cmd),
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                for i in range(self.n)
            ]
        )
        self.semaphore = asyncio.Semaphore(self.n)
        return self

    async def run_job_args_on_worker(self, job_args, worker):
        job_args_bytes = json.dumps(job_args).encode()
        worker.stdin.write(job_args_bytes + b"\n")
        img_bytes = b""
        first_signature_seen = True
        while True:

            data = await worker.stdout.read(1024)  # (b"\n")
            if not data:
                break
            img_bytes += data
            if data.endswith(b"\xff\xd9"):
                break
        return img_bytes

    def close(self):
        for worker in self.workers:
            worker.kill()

    async def messages_to_jpeg(self, message_tuples, width, height, visitors):
        job_args = {
            "width": width,
            "height": height,
            "instructions": [],
            "visitors": visitors,
        }
        for author, message in reversed(list(message_tuples)):
            job_args["instructions"].append({"author": author, "message": message})
        async with self.semaphore:
            worker = self.workers.pop(0)
            try:
                img_bytes = await self.run_job_args_on_worker(job_args, worker)
                return img_bytes
            finally:
                self.workers.append(worker)


if __name__ == "__main__":
    logging.warning("started")
    main()

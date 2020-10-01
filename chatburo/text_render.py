import asyncio


async def render(messages, width=500, height=400, font_color="blue"):
    cmd = (
        [
            "convert",
            f"-size {width}x{height}",
            "xc:lightblue",
            "-font DejaVu-Sans",
            "-pointsize 13",
            f"-fill {font_color}",
            "-gravity NorthWest",
        ]
        + [
            """-draw "text 10,{} '{}'" """.format(index * 30, message)
            for index, message in enumerate(messages)
        ]
        + ["JPEG:-"]
    )
    proc = await asyncio.create_subprocess_shell(
        " ".join(cmd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()
    return stdout

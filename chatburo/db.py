from collections import defaultdict
from asyncio import Queue, Lock
import asyncio
from contextlib import asynccontextmanager
import time
import os
import aiosqlite
from datetime import date, datetime, timedelta
import logging
from collections import deque


def get_current_date_string():
    today = date.today()
    return datetime(year=today.year, month=today.month, day=today.day).isoformat()


def get_current_datetime_string():
    return datetime.now().isoformat()


START_TIMESTAMP = get_current_date_string()


class SqliteBackedPubSub:
    def __init__(self):
        self.TOPICS_REGISTRY = defaultdict(dict)
        self.PUB_SUB_LOCK = Lock()
        self.db = None

    async def connect(self, sqlite_filename):
        self.db = await aiosqlite.connect(sqlite_filename)
        await self.db.execute(
            """
        CREATE TABLE IF NOT EXISTS messages (
            topic TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            message TEXT NOT NULL,
            author TEXT NOT NULL,
            PRIMARY KEY(topic, timestamp)
        );
        """
        )
        await self.db.execute(
            """
        CREATE TABLE IF NOT EXISTS analytics_topicmessages (
            date text NOT NULL,
            topic text NOT NULL,
            count integer default 0,
            PRIMARY KEY(topic, date)
        );
        """
        )
        await self.db.execute(
            """
        CREATE TABLE IF NOT EXISTS analytics_subscribers (
            start text NOT NULL,
            end text default null,
            topic text NOT NULL,
            PRIMARY KEY(topic, start)
        );
        """
        )
        await self.db.commit()
        self.cleanup_task = asyncio.get_event_loop().create_task(self.cleanup())

    async def cleanup(self):
        while True:
            an_hour_ago = datetime.now() - timedelta(hours=1)
            await self.db.execute(
                f"DELETE from messages where date(timestamp) < date(?)",
                [an_hour_ago.isoformat()],
            )
            await self.db.commit()
            logging.warning("cleaned up messages table")
            await asyncio.sleep(1000)

    async def close(self):
        await self.db.close()
        self.cleanup_task.cancel()

    async def publish(self, topic, author, message):
        timestamp = get_current_datetime_string()
        await self.db.execute(
            f"INSERT INTO messages values(?,?,?,?);",
            [topic, timestamp, message, author],
        )
        await self.db.commit()

    async def subscribe(self, topic):
        current_date = get_current_datetime_string()

        try:
            yield 0, None
            messages = deque()
            await self.db.execute(
                """
                INSERT INTO analytics_subscribers (topic, start)
                    VALUES(?, ?);
            """,
                [
                    topic,
                    current_date,
                ],
            )

            await self.db.commit()

            timestamp = START_TIMESTAMP
            async with self.db.execute(
                """
                SELECT author, message, timestamp 
                FROM messages 
                where topic = ?
                order by timestamp desc limit 10;
            """,
                [topic],
            ) as cursor:
                async for row in cursor:
                    messages.appendleft(row[:2])
                    timestamp = row[2]
            got_message_last_time = True
            while True:
                async with self.db.execute(
                    """
                    select count(*)
                    from analytics_subscribers
                    where topic = ? and end is null;
                """,
                    [topic],
                ) as cursor:
                    row = await cursor.fetchone()
                    visitors = int(row[0])

                got_message = False
                async with self.db.execute(
                    """
                    SELECT author, message, timestamp 
                    FROM messages 
                    where topic = ?
                        and datetime(timestamp) > datetime(?)
                    order by timestamp asc;
                """,
                    [topic, timestamp],
                ) as cursor:
                    async for row in cursor:
                        messages.append(row[:2])
                        timestamp = row[2]
                        got_message = True
                while True:
                    try:
                        yield visitors, messages.pop()
                    except IndexError:
                        break

                if got_message != got_message_last_time:
                    yield visitors, None
                    yield visitors, None
                got_message_last_time = got_message
                await asyncio.sleep(1)
        except:
            logging.exception("err")
        finally:
            await self.db.execute(
                """
                UPDATE analytics_subscribers 
                SET end = ?
                where topic = ? and start = ?
            """,
                [get_current_datetime_string(), topic, current_date],
            )

            await self.db.commit()

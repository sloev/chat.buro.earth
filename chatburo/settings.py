from os import environ

REDIS_HOST = environ["REDIS_HOST"]
API_HOSTNAME = "http://localhost:8000"
EXAMPLE_CHAT_HASH = "ZXlKMGVYQWlPaUpLVjFRaUxDSmhiR2NpT2lKSVV6STFOaUo5LmV5SnZjbWxuYVc0aU9tNTFiR3g5LjB3Z0dqNnhrZVM3Z09uSlhPQWhMZkhmTnlnbFJCd1Jqd1lVcGxvUGRXcFU="
CHATBURO_TARGET_NAME = "chatburoworker"
SERVER_SECRET = environ.get("SERVER_SECRET", "foobar")

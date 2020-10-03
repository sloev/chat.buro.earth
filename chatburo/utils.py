import jwt
import base64

from chatburo import settings


def encode(origin=None):
    token_bytes = jwt.encode(
        {"origin": origin}, settings.SERVER_SECRET, algorithm="HS256"
    )
    base64_bytes = base64.b64encode(token_bytes)
    return base64_bytes.decode("ascii")


def decode(b64_token):
    try:
        base64_bytes = b64_token.encode("ascii")
        message_bytes = base64.b64decode(base64_bytes)
        token = message_bytes.decode("ascii")
    except:
        return None
    try:
        return jwt.decode(token, settings.SERVER_SECRET, algorithms=["HS256"])["origin"]
    except jwt.exceptions.DecodeError:
        return None

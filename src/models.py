from pydantic import BaseModel

class ClientData(BaseModel):
    phone_number: str
    name: str


class Conversation(BaseModel):
    user: str
    timestamp: int
    message: str
    stream_sid: str

    
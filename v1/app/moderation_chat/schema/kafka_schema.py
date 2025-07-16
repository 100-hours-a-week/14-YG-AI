from pydantic import BaseModel, Field

def to_camel(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(word.capitalize() for word in parts[1:])


class ChatEvent(BaseModel):
    room_id: int = Field(..., alias="roomId")
    user: str
    content: str

    class Config:
        alias_generator = to_camel
        populate_by_name = True

class ModerationEvent(BaseModel):
    room_id: int = Field(..., alias="roomId")
    message_id: int = Field(..., alias="messageId")
    is_safe: bool = Field(..., alias="isSafe")
    reason: str

    class Config:
        alias_generator = to_camel
        populate_by_name = True


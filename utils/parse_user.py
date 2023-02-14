from pyrogram import Client
from pyrogram.types import Message, User
from pyrogram.enums import MessageEntityType
from pyrogram.errors.exceptions.bad_request_400 import UsernameNotOccupied

from typing import Optional
from enum import Enum


class UserParseStatus(Enum):
    INVALID_MENTION = 0
    NO_REPLY = 1
    OK_MENTION = 2
    OK_REPLY = 3


async def parse_user(bot: Client, message: Message) -> (UserParseStatus, Optional[User]):
    user = None
    has_mention = False
    for ent in message.entities:
        if ent.type == MessageEntityType.TEXT_MENTION:
            user = ent.user
            break
        elif ent.type == MessageEntityType.MENTION:
            try:
                user = await bot.get_users(message.text[ent.offset:ent.offset + ent.length])
            except UsernameNotOccupied:
                pass
            has_mention = True
            break

    if user is not None:
        return UserParseStatus.OK_MENTION, user

    if message.reply_to_message is not None:
        return UserParseStatus.OK_REPLY, message.reply_to_message.from_user

    if has_mention and message.reply_to_message is None:
        return UserParseStatus.INVALID_MENTION, None

    return UserParseStatus.NO_REPLY, None

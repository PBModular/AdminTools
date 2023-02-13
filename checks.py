from pyrogram.types import Message, ChatMember, User
from pyrogram.enums import ChatMemberStatus, MessageEntityType
from pyrogram.errors.exceptions.bad_request_400 import UsernameNotOccupied
from pyrogram import Client
from typing import Optional
from enum import Enum


class UserParseStatus(Enum):
    INVALID_MENTION = 0
    NO_REPLY = 1
    OK_MENTION = 2
    OK_REPLY = 3


async def check_message(self, message: Message) -> Optional[ChatMember]:
    member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
        await message.reply(self.S["not_admin"])
        return

    status, user = await parse_user(self.bot, message)
    if status == UserParseStatus.INVALID_MENTION:
        await message.reply(self.S["user_not_found"], quote=True)
        return

    if status == UserParseStatus.NO_REPLY:
        await message.reply(self.S["no_reply"], quote=True)
        return

    me = await self.bot.get_me()
    me_member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)
    if user.id == me.id or user.id == message.from_user.id:
        await message.reply(self.S["nice_try"])
        return

    if not me_member.privileges.can_restrict_members:
        await message.reply(
            self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
        )

    affect_member = await self.bot.get_chat_member(
        chat_id=message.chat.id, user_id=user.id
    )
    if (affect_member.status == ChatMemberStatus.ADMINISTRATOR or affect_member.status == ChatMemberStatus.OWNER)\
            and not member.status == ChatMemberStatus.OWNER:
        await message.reply(self.S["tried_to_affect_admin"])
        return

    return member


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

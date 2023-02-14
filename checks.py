from pyrogram.types import Message, ChatMember
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant

from .utils import parse_user, UserParseStatus
from typing import Optional


async def ban_check_message(self, message: Message) -> Optional[ChatMember]:
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

    if not me_member.status == ChatMemberStatus.ADMINISTRATOR or not me_member.privileges.can_restrict_members:
        await message.reply(
            self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
        )
        return

    try:
        affect_member = await self.bot.get_chat_member(
            chat_id=message.chat.id, user_id=user.id
        )
    except UserNotParticipant:
        await message.reply(self.S["user_not_found"])
        return

    if (affect_member.status == ChatMemberStatus.ADMINISTRATOR or affect_member.status == ChatMemberStatus.OWNER)\
            and not member.status == ChatMemberStatus.OWNER:
        await message.reply(self.S["tried_to_affect_admin"])
        return

    return member

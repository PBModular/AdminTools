from pyrogram.types import Message, ChatMember, User
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant

from .utils import parse_user, UserParseStatus
from typing import Optional


async def base_checks(self, message: Message, member: ChatMember) -> Optional[User]:
    status, user = await parse_user(self.bot, message)
    if status == UserParseStatus.INVALID_MENTION:
        await message.reply(self.S["user_not_found"], quote=True)
        return

    if status == UserParseStatus.NO_REPLY:
        await message.reply(self.S["no_reply"], quote=True)
        return

    me = await self.bot.get_me()
    if user.id == me.id or user.id == message.from_user.id:
        await message.reply(self.S["nice_try"])
        return

    return user


async def restrict_check_message(self, message: Message) -> Optional[User]:
    member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    user = await base_checks(self, message, member)
    if user is None:
        return

    if not (member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}):
        await message.reply(self.S["not_admin"])
        return

    if not member.privileges.can_restrict_members:
        await message.reply(self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>")
        return

    me = await self.bot.get_me()
    me_member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)
    
    if (me_member.status not in {ChatMemberStatus.ADMINISTRATOR} or not me_member.privileges.can_restrict_members):
        await message.reply(self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>")
        return

    try:
        affect_member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=user.id)
    except UserNotParticipant:
        await message.reply(self.S["user_not_found"])
        return

    if (affect_member.status in {ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER} and member.status != ChatMemberStatus.OWNER):
        await message.reply(self.S["tried_to_affect_admin"])
        return

    return user

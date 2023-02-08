from pyrogram.types import Message, ChatMember
from pyrogram.enums import ChatMemberStatus
from typing import Optional


async def check_message(self, message: Message) -> Optional[ChatMember]:
    member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
        await message.reply(self.S["not_admin"])
        return

    if message.reply_to_message is None:
        await message.reply(self.S["no_reply"])
        return

    to_id = message.reply_to_message.from_user.id
    me = await self.bot.get_me()
    me_member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)
    if to_id == me.id or to_id == message.from_user.id:
        await message.reply(self.S["nice_try"])
        return

    if not me_member.privileges.can_restrict_members:
        await message.reply(
            self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
        )

    affect_member = await self.bot.get_chat_member(
        chat_id=message.chat.id, user_id=to_id
    )
    if (affect_member.status == ChatMemberStatus.ADMINISTRATOR or affect_member.status == ChatMemberStatus.OWNER)\
            and not member.status == ChatMemberStatus.OWNER:
        await message.reply(self.S["tried_to_affect_admin"])
        return

    return member

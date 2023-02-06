from aiogram.types import Message, ChatMember
from typing import Optional


async def check_message(self, message: Message) -> Optional[ChatMember]:
    member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
    if not (member.status == 'administrator' or member.status == 'creator'):
        await message.reply(self.S["not_admin"])
        return

    if message.reply_to_message is None:
        await message.reply(self.S["no_reply"])
        return

    to_id = message.reply_to_message.from_user.id
    me = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=self.bot.id)
    if to_id == self.bot.id or to_id == message.from_user.id:
        await message.reply(self.S["nice_try"])
        return

    if not me.can_restrict_members:
        await message.reply(
            self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
        )

    affect_member = await self.bot.get_chat_member(
        chat_id=message.chat.id, user_id=to_id
    )
    if (affect_member.status == 'administrator' or affect_member.status == 'creator') and not member.status == "creator":
        await message.reply(self.S["tried_to_affect_admin"])
        return

    return member

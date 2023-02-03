from base.module import BaseModule, ModuleInfo, command
from aiogram.types import Message, ChatMember
from typing import Optional


class AdminModule(BaseModule):
    @property
    def module_info(self) -> ModuleInfo:
        return ModuleInfo(
            name="AdminTools",
            author="SanyaPilot",
            version="0.0.1",
            src_url="https://github.com/PBModular/admin_tools_module"
        )

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

    async def ban_generic_checks(self, message: Message) -> bool:
        member = await self.check_message(message)
        if member is None:
            return False

        if not member.can_restrict_members and member.status == 'administrator':
            await message.reply(
                self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
            )
            return False

        return True

    @command("ban")
    async def ban_cmd(self, message: Message):
        if not await self.ban_generic_checks(message):
            return

        await self.bot.ban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.full_name
        await message.reply(self.S["ban"].format(name))

    @command("unban")
    async def unban_cmd(self, message: Message):
        if not message.chat.type == "supergroup":
            await message.reply(self.S["not_supergroup"])
            return

        if not await self.ban_generic_checks(message):
            return

        await self.bot.unban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.full_name
        await message.reply(self.S["unban"].format(name))

    @command("kick")
    async def kick_cmd(self, message: Message):
        if not message.chat.type == "supergroup":
            await message.reply(self.S["not_supergroup"])
            return

        if not await self.ban_generic_checks(message):
            return

        await self.bot.ban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)
        await self.bot.unban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.full_name
        await message.reply(self.S["kick"].format(name))

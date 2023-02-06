from base.mod_ext import ModuleExtension
from base.module import command
from .checks import check_message
from aiogram.types import Message


class BanExtension(ModuleExtension):
    async def ban_generic_checks(self, message: Message) -> bool:
        member = await check_message(self, message)
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

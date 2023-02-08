from base.mod_ext import ModuleExtension
from base.module import command
from .checks import check_message
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus


class BanExtension(ModuleExtension):
    async def ban_generic_checks(self, message: Message) -> bool:
        member = await check_message(self, message)
        if member is None:
            return False

        if not member.privileges.can_restrict_members and member.status == ChatMemberStatus.ADMINISTRATOR:
            await message.reply(
                self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
            )
            return False

        return True

    @command("ban")
    async def ban_cmd(self, bot: Client, message: Message):
        if not await self.ban_generic_checks(message):
            return

        await bot.ban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["ban"].format(name), quote=True)

    @command("unban")
    async def unban_cmd(self, bot: Client, message: Message):
        if not message.chat.type == ChatType.SUPERGROUP:
            await message.reply(self.S["not_supergroup"])
            return

        if not await self.ban_generic_checks(message):
            return

        await bot.unban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["unban"].format(name), quote=True)

    @command("kick")
    async def kick_cmd(self, bot: Client, message: Message):
        if not message.chat.type == ChatType.SUPERGROUP:
            await message.reply(self.S["not_supergroup"])
            return

        if not await self.ban_generic_checks(message):
            return

        await bot.ban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=message.reply_to_message.from_user.id)

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["kick"].format(name), quote=True)

from base.mod_ext import ModuleExtension
from base.module import command
from ..checks import check_message
from ..utils import parse_timedelta
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus
from datetime import datetime
from babel.dates import format_timedelta


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

    @command("ban", filters.group)
    async def ban_cmd(self, bot: Client, message: Message):
        if not await self.ban_generic_checks(message):
            return

        args = message.text.split()
        delta = None
        if len(args) > 1:
            delta = parse_timedelta(args)
            if delta is None:
                await message.reply(self.S["ban"]["illegal_usage"])
                return

        await bot.ban_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            until_date=(datetime.now() + delta) if delta else datetime.fromtimestamp(0)
        )

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.first_name

        if delta is None:
            await message.reply(self.S["ban"]["ok_forever"].format(user=name), quote=True)
        else:
            await message.reply(
                self.S["ban"]["ok"].format(
                    user=name,
                    time=format_timedelta(delta, locale=self.cur_lang, format="long")
                ),
                quote=True
            )

    @command("unban", filters.group)
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

    @command("kick", filters.group)
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

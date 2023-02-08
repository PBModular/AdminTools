from base.mod_ext import ModuleExtension
from base.module import command
from .checks import check_message
from .utils import parse_timedelta
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from datetime import datetime
from babel.dates import format_timedelta


class MuteExtension(ModuleExtension):
    async def mute_generic_checks(self, message: Message) -> bool:
        member = await check_message(self, message)
        if member is None:
            return False

        if not member.privileges.can_restrict_members and member.status == ChatMemberStatus.ADMINISTRATOR:
            await message.reply(
                self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>",
                quote=True
            )
            return False

        return True

    @command("mute", filters.group)
    async def mute_cmd(self, bot: Client, message: Message):
        if not await self.mute_generic_checks(message):
            return

        args = message.text.split()
        delta = None
        if len(args) > 1:
            delta = parse_timedelta(args)
            if delta is None:
                await message.reply(self.S["mute"]["illegal_usage"])
                return

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=(datetime.now() + delta) if delta else datetime.fromtimestamp(0)
        )
        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.first_name

        if delta is None:
            await message.reply(self.S["mute"]["ok_forever"].format(user=name), quote=True)
        else:
            await message.reply(
                self.S["mute"]["ok"].format(
                    user=name,
                    time=format_timedelta(delta, locale=self.cur_lang, format="long")
                ),
                quote=True
            )

    @command("unmute", filters.group)
    async def unmute_cmd(self, bot: Client, message: Message):
        if not await self.mute_generic_checks(message):
            return

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=message.chat.permissions
        )

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["unmute"].format(user=name))

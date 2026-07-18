from base.mod_ext import ModuleExtension
from base.module import command
from ..checks import restrict_check_message
from ..utils import parse_timedelta, parse_user, UserParseStatus
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from pyrogram.enums import ChatMemberStatus
from datetime import datetime
from babel.dates import format_timedelta


class MuteExtension(ModuleExtension):
    @command("mute", filters.group)
    async def mute_cmd(self, bot: Client, message: Message):
        if await restrict_check_message(self, message) is None:
            return

        status, user = await parse_user(bot, message)

        args = message.text.split()
        delta = None
        if len(args) > (1 if status == UserParseStatus.OK_REPLY else 2):
            delta = parse_timedelta(args)
            if delta is None:
                await message.reply(self.S["mute"]["illegal_usage"])
                return

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=(datetime.now() + delta) if delta else datetime.fromtimestamp(0)
        )

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
        user = await restrict_check_message(self, message)
        if user is None:
            return

        name = f"@{user.username}" if user.username else user.first_name

        affect_member = await bot.get_chat_member(chat_id=message.chat.id, user_id=user.id)
        is_muted = (
            affect_member.status == ChatMemberStatus.RESTRICTED
            and affect_member.permissions is not None
            and not affect_member.permissions.can_send_messages
        )
        if not is_muted:
            await message.reply(self.S["mute"]["not_muted"].format(user=name), quote=True)
            return

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=message.chat.permissions
        )

        await message.reply(self.S["unmute"].format(user=name))

from base.mod_ext import ModuleExtension
from base.module import command
from .checks import check_message
from aiogram.types import Message, ChatPermissions
from datetime import timedelta
from babel.dates import format_timedelta

TIME_MULTIPLIERS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

class MuteExtension(ModuleExtension):
    async def mute_generic_checks(self, message: Message) -> bool:
        member = await check_message(self, message)
        if member is None:
            return False

        if not member.can_restrict_members and member.status == 'administrator':
            await message.reply(
                self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
            )
            return False

        return True

    @command("mute")
    async def mute_cmd(self, message: Message):
        if not await self.mute_generic_checks(message):
            return

        args = message.text.split()
        delta = 0
        if len(args) > 1:
            quantity, unit = int(args[-1][:-1]), args[-1][-1:]
            if unit not in ("s", "m", "h", "d"):
                await message.reply(self.S["mute"]["illegal_usage"])
                return

            if unit == "d":
                delta = timedelta(days=quantity)
            elif unit == "h":
                delta = timedelta(hours=quantity)
            elif unit == "m":
                delta = timedelta(minutes=quantity)
            elif unit == "s":
                delta = timedelta(seconds=quantity)

        await self.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=delta
        )
        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.full_name

        if delta == 0:
            await message.reply(self.S["mute"]["ok_forever"].format(user=name))
        else:
            await message.reply(
                self.S["mute"]["ok"].format(
                    user=name,
                    time=format_timedelta(delta, locale=self.cur_lang, format="long")
                )
            )

    @command("unmute")
    async def unmute_cmd(self, message: Message):
        if not await self.mute_generic_checks(message):
            return

        await self.bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.reply_to_message.from_user.id,
            permissions=(await self.bot.get_chat(chat_id=message.chat.id)).permissions
        )

        user = message.reply_to_message.from_user
        name = f"@{user.username}" if user.username else user.full_name
        await message.reply(self.S["unmute"].format(user=name))

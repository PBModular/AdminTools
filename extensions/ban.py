from base.mod_ext import ModuleExtension
from base.module import command
from ..checks import restrict_check_message
from ..utils import parse_timedelta, parse_user, UserParseStatus
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatType, ChatMemberStatus
from datetime import datetime
from babel.dates import format_timedelta


class BanExtension(ModuleExtension):
    @command("ban", filters.group)
    async def ban_cmd(self, bot: Client, message: Message):
        if await restrict_check_message(self, message) is None:
            return

        status, user = await parse_user(bot, message)

        args = message.text.split()
        delta = None
        if len(args) > (1 if status == UserParseStatus.OK_REPLY else 2):
            delta = parse_timedelta(args)
            if delta is None:
                await message.reply(self.S["ban"]["illegal_usage"])
                return

        await bot.ban_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            until_date=(datetime.now() + delta) if delta else datetime.fromtimestamp(0)
        )

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

        user = await restrict_check_message(self, message)
        if user is None:
            return

        await bot.unban_chat_member(chat_id=message.chat.id, user_id=user.id)

        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["unban"].format(name), quote=True)

    @command("kick", filters.group)
    async def kick_cmd(self, bot: Client, message: Message):
        if not message.chat.type == ChatType.SUPERGROUP:
            await message.reply(self.S["not_supergroup"])
            return

        user = await restrict_check_message(self, message)
        if user is None:
            return

        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user.id)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=user.id)

        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["kick"].format(name), quote=True)

    @command("kickme", filters.group)
    async def kickme_cmd(self, bot: Client, message: Message):
        if not message.chat.type == ChatType.SUPERGROUP:
            await message.reply(self.S["not_supergroup"])
            return

        await self.banme_cmd(bot, message)
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)

    @command("banme", filters.group)
    async def banme_cmd(self, bot: Client, message: Message):
        me = await bot.get_me()
        me_member = await bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)
        if not me_member.privileges.can_restrict_members:
            await message.reply(
                self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
            )
            return

        user = message.from_user
        affect_member = await bot.get_chat_member(chat_id=message.chat.id, user_id=user.id)
        if affect_member.status == ChatMemberStatus.ADMINISTRATOR or affect_member.status == ChatMemberStatus.OWNER:
            await message.reply(self.S["tried_to_affect_admin"])
            return

        name = f"@{user.username}" if user.username else user.first_name
        await message.reply(self.S["affect_self"] + "\n" + self.S["ban"]["ok_forever"].format(user=name))

        await bot.ban_chat_member(chat_id=message.chat.id, user_id=user.id)

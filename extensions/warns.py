from pyrogram import Client
from pyrogram import filters
from pyrogram.types import Message, CallbackQuery, User, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant

from sqlalchemy import select

from base.mod_ext import ModuleExtension
from base.module import command, callback_query
from ..checks import base_checks
from ..db import ChatSettings, Warns
from ..config import DefaultWarnSettings
from ..utils import parse_time, parse_user, UserParseStatus

import time
from datetime import datetime, timedelta
from typing import Optional
from babel.dates import format_timedelta

ALLOWED_MODES = ("kick", "ban", "mute")


class WarnsExtension(ModuleExtension):
    async def check_msg(self, message: Message) -> Optional[User]:
        member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        user = await base_checks(self, message, member)
        if user is None:
            return

        me = await self.bot.get_me()
        me_member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)
        if not me_member.status == ChatMemberStatus.ADMINISTRATOR or not me_member.privileges.can_restrict_members:
            await message.reply(
                self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>"
            )
            return

        try:
            affect_member = await self.bot.get_chat_member(
                chat_id=message.chat.id, user_id=user.id
            )
        except UserNotParticipant:
            await message.reply(self.S["user_not_found"])
            return

        if (affect_member.status == ChatMemberStatus.ADMINISTRATOR or affect_member.status == ChatMemberStatus.OWNER) \
                and not member.status == ChatMemberStatus.OWNER:
            await message.reply(self.S["tried_to_affect_admin"])
            return

        return user

    @command("warn", filters.group)
    async def warn_cmd(self, bot: Client, message: Message):
        user = await self.check_msg(message)
        if user is None:
            return

        db_settings = self.db.session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
        if db_settings is None:
            return

        db_user = self.db.session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
        if db_user is None:
            db_user = Warns(chat_id=message.chat.id, user_id=user.id, count=0)
            self.db.session.add(db_user)

        name = f"@{user.username}" if user.username else user.first_name

        db_user.count += 1
        if db_user.count >= db_settings.warn_limit:
            text = f"{self.S['warn']['restrict_header']} \n{name} "
            if db_settings.warn_restriction == "mute":
                await bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=datetime.fromtimestamp(time.time() + db_settings.warn_rest_time)
                )
                if db_settings.warn_rest_time < 30:
                    text += self.S["warn"]["restrictions"]["mute"]
                else:
                    delta = timedelta(seconds=db_settings.warn_rest_time)
                    text += self.S["warn"]["restrictions"]["tmute"].format(
                        time=format_timedelta(delta, locale=self.cur_lang, format="long")
                    )

            elif db_settings.warn_restriction == "ban":
                await bot.ban_chat_member(
                    chat_id=message.chat.id,
                    user_id=user.id,
                    until_date=datetime.fromtimestamp(time.time() + db_settings.warn_rest_time)
                )
                if db_settings.warn_rest_time < 30:
                    text += self.S["warn"]["restrictions"]["ban"]
                else:
                    delta = timedelta(seconds=db_settings.warn_rest_time)
                    text += self.S["warn"]["restrictions"]["tban"].format(
                        time=format_timedelta(delta, locale=self.cur_lang, format="long")
                    )

            elif db_settings.warn_restriction == "kick":
                await bot.ban_chat_member(chat_id=message.chat.id, user_id=user.id)
                await bot.unban_chat_member(chat_id=message.chat.id, user_id=user.id)
                text += self.S["warn"]["restrictions"]["kick"]

            else:
                self.logger.error(f"WTF unsupported restriction for warn!")
                return

            await message.reply(text)
            self.db.session.delete(db_user)

        else:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text=self.S["warn"]["button"], callback_data=f"remove_warn:{user.id}")]]
            )
            await message.reply(
                self.S["warn"]["msg"].format(user=name, cur=db_user.count, total=db_settings.warn_limit),
                reply_markup=keyboard
            )

        self.db.session.commit()

    @callback_query(filters.regex("remove_warn"))
    async def remove_warn(self, bot: Client, call: CallbackQuery):
        member = await bot.get_chat_member(chat_id=call.message.chat.id, user_id=call.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await call.answer(self.S["not_admin_call"])
            return

        user_id = int(call.data.split(":")[1])
        user = await bot.get_users(user_id)
        user_name = f"@{user.username}" if user.username else user.first_name

        db_user: Warns = self.db.session.scalar(select(Warns).filter_by(chat_id=call.message.chat.id, user_id=user_id))
        if db_user is None or db_user.count == 0:
            await call.answer(self.S["warn"]["no_warns_call"].format(user=user_name))
            return

        db_user.count -= 1
        self.db.session.commit()

        await call.answer()
        admin_name = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        await call.message.edit_text(self.S["warn"]["remove_call"].format(admin=admin_name, user=user_name))

    @command("warns", filters.group)
    async def warns_cmd(self, _, message: Message):
        status, user = await parse_user(self.bot, message)
        if status == UserParseStatus.INVALID_MENTION:
            await message.reply(self.S["user_not_found"], quote=True)
            return

        if status == UserParseStatus.NO_REPLY:
            user = message.from_user
        else:
            me = await self.bot.get_me()
            if user.id == me.id or user.id == message.from_user.id:
                await message.reply(self.S["nice_try"])
                return

        name = f"@{user.username}" if user.username else user.first_name

        db_user: Warns = self.db.session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
        if db_user is None or db_user.count == 0:
            await message.reply(self.S["warn"]["no_warns_call"].format(user=name))
            return

        warn_limit = self.db.session.scalar(select(ChatSettings.warn_limit).filter_by(chat_id=message.chat.id))
        if warn_limit is None:
            return

        await message.reply(self.S["warn"]["status"].format(
            user=name, cur=db_user.count, total=warn_limit
        ))

    @command("resetwarns", filters.group)
    async def reset_warns_cmd(self, _, message: Message):
        user = await self.check_msg(message)
        if user is None:
            return

        name = f"@{user.username}" if user.username else user.first_name

        db_user = self.db.session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
        if db_user is None or db_user.count == 0:
            await message.reply(self.S["warn"]["no_warns"].format(user=name))
            return

        db_user.count = 0
        self.db.session.commit()

        await message.reply(self.S["warn"]["reset"].format(user=name))

    @command("rmwarn", filters.group)
    async def rmwarn_cmd(self, _, message: Message):
        user = await self.check_msg(message)
        if user is None:
            return

        name = f"@{user.username}" if user.username else user.first_name

        warn_limit = self.db.session.scalar(select(ChatSettings.warn_limit).filter_by(chat_id=message.chat.id))
        if warn_limit is None:
            return

        db_user = self.db.session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
        if db_user is None or db_user.count == 0:
            await message.reply(self.S["warn"]["no_warns"].format(user=name))
            return

        db_user.count -= 1
        self.db.session.commit()

        await message.reply(self.S["warn"]["remove_msg"].format(
            user=name,
            cur=db_user.count,
            total=warn_limit
        ))

    @command("setwarnmode", filters.group)
    async def set_warn_mode_cmd(self, bot: Client, message: Message):
        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"])
            return

        args = message.text.split()[1:]
        if len(args) == 0:
            await message.reply(self.S["warn"]["set_mode"]["illegal_usage"])
            return

        mode = args[0]
        mode_time = None
        if len(args) > 1:
            mode_time = parse_time(args[-1])
            if mode_time is None:
                await message.reply(self.S["warn"]["set_mode"]["illegal_usage"])
                return
            if mode_time < 30:
                mode_time = None

        if mode not in ALLOWED_MODES:
            await message.reply(self.S["warn"]["set_mode"]["illegal_usage"])
            return

        db_settings = self.db.session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
        if db_settings is None:
            return

        db_settings.warn_restriction = mode
        db_settings.warn_rest_time = mode_time if mode_time else 0

        self.db.session.commit()

        text = self.S["warn"]["set_mode"]["ok_header"] + "\n" + self.S["warn"]["set_mode"]["modes"][mode]
        if mode_time is not None:
            text += " " + self.S["warn"]["set_mode"]["timed"].format(
                time=format_timedelta(timedelta(seconds=mode_time), locale=self.cur_lang, format="long")
            )

        await message.reply(text)

    @command("setwarnlimit", filters.group)
    async def set_warn_limit(self, bot: Client, message: Message):
        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"])
            return

        args = message.text.split()[1:]
        if len(args) == 0:
            await message.reply(self.S["warn"]["set_limit"]["illegal_usage"])
            return

        try:
            limit = int(args[-1])
        except ValueError:
            await message.reply(self.S["warn"]["set_limit"]["illegal_usage"])
            return

        if limit < 0:
            await message.reply(self.S["warn"]["set_limit"]["illegal_usage"])
            return

        db_settings = self.db.session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
        if db_settings is None:
            return

        db_settings.warn_limit = limit
        self.db.session.commit()

        await message.reply(self.S["warn"]["set_limit"]["ok"].format(total=db_settings.warn_limit))

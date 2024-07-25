from datetime import datetime, timedelta
import time
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, User, ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from sqlalchemy import select

from base.mod_ext import ModuleExtension
from base.module import command, callback_query
from ..checks import base_checks
from ..db import ChatSettings, Warns
from ..utils import parse_time, parse_user, UserParseStatus

from babel.dates import format_timedelta

ALLOWED_MODES = ("kick", "ban", "mute")


class WarnsExtension(ModuleExtension):

    async def check_msg(self, message: Message) -> Optional[User]:
        member = await self.bot.get_chat_member(message.chat.id, message.from_user.id)
        user = await base_checks(self, message, member)
        
        if not user:
            return None

        me = await self.bot.get_me()
        me_member = await self.bot.get_chat_member(message.chat.id, me.id)
        
        if me_member.status != ChatMemberStatus.ADMINISTRATOR or not me_member.privileges.can_restrict_members:
            await message.reply(f"{self.S['bot_insufficient_rights']} - <code>{self.S['rights']['restrict_members']}</code>")
            return None

        try:
            affect_member = await self.bot.get_chat_member(message.chat.id, user.id)
        except UserNotParticipant:
            await message.reply(self.S["user_not_found"])
            return None

        if (affect_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]) and member.status != ChatMemberStatus.OWNER:
            await message.reply(self.S["tried_to_affect_admin"])
            return None

        return user

    @command("warn", filters.group)
    async def warn_cmd(self, bot: Client, message: Message):
        user = await self.check_msg(message)
        if not user:
            return

        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if not db_settings:
                return

            db_user = await session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
            if not db_user:
                db_user = Warns(chat_id=message.chat.id, user_id=user.id, count=0)
                session.add(db_user)

            name = f"@{user.username}" if user.username else user.first_name
            db_user.count += 1

            if db_user.count >= db_settings.warn_limit:
                await self.apply_restriction(bot, message, user, db_settings, db_user.count, name)
                await session.delete(db_user)
            else:
                keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(text=self.S["warn"]["button"], callback_data=f"remove_warn:{user.id}")]])
                await message.reply(self.S["warn"]["msg"].format(user=name, cur=db_user.count, total=db_settings.warn_limit), reply_markup=keyboard)

            await session.commit()

    async def apply_restriction(self, bot: Client, message: Message, user: User, db_settings: ChatSettings, count: int, name: str):
        text = f"{self.S['warn']['restrict_header']} \n{name} "
        restriction_time = db_settings.warn_rest_time
        time_delta = timedelta(seconds=restriction_time)

        if db_settings.warn_restriction == "mute":
            await bot.restrict_chat_member(
                message.chat.id, user.id, permissions=ChatPermissions(can_send_messages=False), 
                until_date=datetime.fromtimestamp(time.time() + restriction_time))
            text += self.S["warn"]["restrictions"]["tmute"].format(
                time=format_timedelta(time_delta, locale=self.cur_lang, format="long")) if restriction_time >= 30 else self.S["warn"]["restrictions"]["mute"]
        elif db_settings.warn_restriction == "ban":
            await bot.ban_chat_member(
                message.chat.id, user.id, 
                until_date=datetime.fromtimestamp(time.time() + restriction_time))
            text += self.S["warn"]["restrictions"]["tban"].format(
                time=format_timedelta(time_delta, locale=self.cur_lang, format="long")) if restriction_time >= 30 else self.S["warn"]["restrictions"]["ban"]
        elif db_settings.warn_restriction == "kick":
            await bot.ban_chat_member(message.chat.id, user.id)
            await bot.unban_chat_member(message.chat.id, user.id)
            text += self.S["warn"]["restrictions"]["kick"]
        else:
            self.logger.error("Unsupported restriction for warn!")
            return

        await message.reply(text)

    @callback_query(filters.regex("remove_warn"))
    async def remove_warn(self, bot: Client, call: CallbackQuery):
        member = await bot.get_chat_member(call.message.chat.id, call.from_user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await call.answer(self.S["not_admin_call"])
            return

        user_id = int(call.data.split(":")[1])
        user = await bot.get_users(user_id)
        user_name = f"@{user.username}" if user.username else user.first_name

        async with self.db.session_maker() as session:
            db_user = await session.scalar(select(Warns).filter_by(chat_id=call.message.chat.id, user_id=user_id))
            if not db_user or db_user.count == 0:
                await call.answer(self.S["warn"]["no_warns_call"].format(user=user_name))
                return

            db_user.count -= 1
            await session.commit()

        await call.answer()
        admin_name = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name
        await call.message.edit_text(self.S["warn"]["remove_call"].format(admin=admin_name, user=user_name))

    @command("warns", filters.group)
    async def warns_cmd(self, bot: Client, message: Message):
        status, user = await parse_user(bot, message)
        if status == UserParseStatus.INVALID_MENTION:
            await message.reply(self.S["user_not_found"], quote=True)
            return

        user = user if status != UserParseStatus.NO_REPLY else message.from_user
        me = await self.bot.get_me()
        
        if user.id == me.id:
            await message.reply(self.S["nice_try"])
            return

        name = f"@{user.username}" if user.username else user.first_name

        async with self.db.session_maker() as session:
            db_user = await session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
            warn_limit = await session.scalar(select(ChatSettings.warn_limit).filter_by(chat_id=message.chat.id))
            if not db_user or db_user.count == 0:
                await message.reply(self.S["warn"]["no_warns_call"].format(user=name))
            elif warn_limit:
                await message.reply(self.S["warn"]["status"].format(user=name, cur=db_user.count, total=warn_limit))

    @command("resetwarns", filters.group)
    async def reset_warns_cmd(self, bot: Client, message: Message):
        user = await self.check_msg(message)
        if not user:
            return

        name = f"@{user.username}" if user.username else user.first_name

        async with self.db.session_maker() as session:
            db_user = await session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
            if not db_user or db_user.count == 0:
                await message.reply(self.S["warn"]["no_warns"].format(user=name))
                return

            db_user.count = 0
            await session.commit()

        await message.reply(self.S["warn"]["reset"].format(user=name))

    @command("rmwarn", filters.group)
    async def rmwarn_cmd(self, bot: Client, message: Message):
        user = await self.check_msg(message)
        if not user:
            return

        name = f"@{user.username}" if user.username else user.first_name

        async with self.db.session_maker() as session:
            warn_limit = await session.scalar(select(ChatSettings.warn_limit).filter_by(chat_id=message.chat.id))
            if not warn_limit:
                return

            db_user = await session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
            if not db_user or db_user.count == 0:
                await message.reply(self.S["warn"]["no_warns"].format(user=name))
                return

            db_user.count -= 1
            await session.commit()

            await message.reply(self.S["warn"]["remove_msg"].format(user=name, cur=db_user.count, total=warn_limit))

    @command("setwarnmode", filters.group)
    async def set_warn_mode_cmd(self, bot: Client, message: Message):
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply(self.S["not_admin"])
            return

        args = message.text.split()[1:]
        if not args:
            await message.reply(self.S["warn"]["set_mode"]["illegal_usage"])
            return

        mode, mode_time = args[0], parse_time(args[-1]) if len(args) > 1 else None
        if mode not in ALLOWED_MODES or (mode_time is not None and mode_time < 30):
            await message.reply(self.S["warn"]["set_mode"]["illegal_usage"])
            return

        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if not db_settings:
                return

            db_settings.warn_restriction = mode
            db_settings.warn_rest_time = mode_time or 0
            await session.commit()

        text = f"{self.S['warn']['set_mode']['ok_header']}\n{self.S['warn']['set_mode']['modes'][mode]}"
        if mode_time:
            text += f" {self.S['warn']['set_mode']['timed'].format(time=format_timedelta(timedelta(seconds=mode_time), locale=self.cur_lang, format='long'))}"
        await message.reply(text)

    @command("setwarnlimit", filters.group)
    async def set_warn_limit_cmd(self, bot: Client, message: Message):
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply(self.S["not_admin"])
            return

        args = message.text.split()[1:]
        if not args:
            await message.reply(self.S["warn"]["set_limit"]["illegal_usage"])
            return

        try:
            limit = int(args[0])
        except ValueError:
            await message.reply(self.S["warn"]["set_limit"]["illegal_usage"])
            return

        if limit < 0:
            await message.reply(self.S["warn"]["set_limit"]["illegal_usage"])
            return

        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if not db_settings:
                return

            db_settings.warn_limit = limit
            await session.commit()

        await message.reply(self.S["warn"]["set_limit"]["ok"].format(total=limit))

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
from ..checks import restrict_check_message
from ..db import ChatSettings, Warns
from ..utils import parse_time, parse_user, UserParseStatus

from babel.dates import format_timedelta

ALLOWED_MODES = ("kick", "ban", "mute")


class WarnsExtension(ModuleExtension):
    @command("warn", filters.group)
    async def warn_cmd(self, bot: Client, message: Message):
        user = await restrict_check_message(self, message)
        if not user:
            return

        if message.reply_to_message:
            args = message.text.split(maxsplit=1)
            reason = args[1].split()[:10] if len(args) > 1 else self.S["warn"]["no_reason"]
        else:
            args = message.text.split(maxsplit=2)
            reason = args[2] if len(args) > 2 else self.S["warn"]["no_reason"]

        status = await self._warn_user(bot, message.chat.id, user.id, reason)
        if status.get("error"):
            await message.reply("Error: Chat settings not found.")
            return

        name = f"@{user.username}" if user.username else user.first_name
        if status["limit_reached"]:
            await message.reply(
                f"{self.S['warn']['restrict_header']}\n{name} has been {status['restriction']} for reaching the warning limit."
            )
        else:
            keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(
                text=self.S["warn"]["button"], callback_data=f"remove_warn:{user.id}"
            )]])
            await message.reply(
                self.S["warn"]["msg"].format(user=name, cur=status["warn_count"], total=status["warn_limit"], reason=reason),
                reply_markup=keyboard
            )

    async def _apply_restriction(self, bot: Client, chat_id: int, user_id: int, db_settings: ChatSettings):
        restriction = db_settings.warn_restriction
        restriction_time = db_settings.warn_rest_time
        until_date = (datetime.now() + timedelta(seconds=restriction_time)) if restriction_time > 0 else datetime.fromtimestamp(0)
        
        if restriction == "mute":
            await bot.restrict_chat_member(
                chat_id, user_id, permissions=ChatPermissions(can_send_messages=False), until_date=until_date
            )
        elif restriction == "ban":
            await bot.ban_chat_member(chat_id, user_id, until_date=until_date)
        elif restriction == "kick":
            await bot.ban_chat_member(chat_id, user_id)
            await bot.unban_chat_member(chat_id, user_id)
        return restriction

    async def _warn_user(self, bot: Client, chat_id: int, user_id: int, reason: str):
        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=chat_id))
            if not db_settings:
                return {"error": "settings_not_found"}
            
            db_user = await session.scalar(select(Warns).filter_by(chat_id=chat_id, user_id=user_id))
            if not db_user:
                db_user = Warns(chat_id=chat_id, user_id=user_id, count=0)
                session.add(db_user)
            else:
                if db_settings.warn_autoreset and db_settings.warn_autoreset_time > 0 and db_user.last_warn_time:
                    last_warn = datetime.fromisoformat(db_user.last_warn_time)
                    reset_threshold = last_warn + timedelta(seconds=db_settings.warn_autoreset_time)
                    if datetime.now() > reset_threshold:
                        db_user.count = 0
                        db_user.reasons = ""
                        db_user.dates = ""

            db_user.count += 1
            current_date = datetime.now().strftime("%Y.%m.%d %H:%M")
            db_user.last_warn_time = datetime.now().isoformat()
            db_user.reasons = f"{db_user.reasons},{reason}" if db_user.reasons else reason
            db_user.dates = f"{db_user.dates},{current_date}" if db_user.dates else current_date

            if db_user.count >= db_settings.warn_limit:
                restriction = await self._apply_restriction(bot, chat_id, user_id, db_settings)
                await session.delete(db_user)
                await session.commit()
                return {
                    "warn_count": db_user.count,
                    "warn_limit": db_settings.warn_limit,
                    "limit_reached": True,
                    "restriction": restriction
                }
            else:
                await session.commit()
                return {
                    "warn_count": db_user.count,
                    "warn_limit": db_settings.warn_limit,
                    "limit_reached": False,
                    "restriction": None
                }

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

            reasons = db_user.reasons.split(",")
            dates = db_user.dates.split(",")
            reasons.pop()
            dates.pop()

            db_user.count -= 1
            db_user.reasons = ",".join(reasons)
            db_user.dates = ",".join(dates)
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
                reasons = db_user.reasons.split(",")
                dates = db_user.dates.split(",")
                
                warn_list = "\n".join([f"{i+1}. <code>{dates[i]}</code>, {self.S["warn"]["reason"]} {reasons[i]}" for i in range(len(reasons))])
                await message.reply(self.S["warn"]["status"].format(user=name, cur=db_user.count, total=warn_limit, warn_list=warn_list))

    @command("resetwarns", filters.group)
    async def reset_warns_cmd(self, bot: Client, message: Message):
        user = await restrict_check_message(self, message)
        if not user:
            return

        name = f"@{user.username}" if user.username else user.first_name

        async with self.db.session_maker() as session:
            db_user = await session.scalar(select(Warns).filter_by(chat_id=message.chat.id, user_id=user.id))
            if not db_user or db_user.count == 0:
                await message.reply(self.S["warn"]["no_warns"].format(user=name))
                return

            db_user.count = 0
            db_user.reasons = ""
            db_user.dates = ""
            await session.commit()

        await message.reply(self.S["warn"]["reset"].format(user=name))

    @command("rmwarn", filters.group)
    async def rmwarn_cmd(self, bot: Client, message: Message):
        user = await restrict_check_message(self, message)
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

            reasons = db_user.reasons.split(",")
            dates = db_user.dates.split(",")
            reasons.pop()
            dates.pop()

            db_user.count -= 1
            db_user.reasons = ",".join(reasons)
            db_user.dates = ",".join(dates)
            await session.commit()

            await message.reply(self.S["warn"]["remove_msg"].format(user=name, cur=db_user.count, total=warn_limit))

    @command("warnautoreset", filters.group)
    async def check_autoreset_cmd(self, bot: Client, message: Message):
        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if not db_settings:
                return
            
            if not hasattr(db_settings, 'warn_autoreset'):
                await message.reply(self.S["warn"]["autoreset"]["not_configured"])
                return
                
            if not db_settings.warn_autoreset:
                await message.reply(self.S["warn"]["autoreset"]["status_disabled"])
            else:
                if db_settings.warn_autoreset_time > 0:
                    time_text = format_timedelta(timedelta(seconds=db_settings.warn_autoreset_time), locale=self.cur_lang, format='long')
                    await message.reply(self.S["warn"]["autoreset"]["status_enabled_with_time"].format(time=time_text))
                else:
                    await message.reply(self.S["warn"]["autoreset"]["status_enabled"])

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

    @command("setwarnautoreset", filters.group)
    async def set_autoreset_cmd(self, bot: Client, message: Message):
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await message.reply(self.S["not_admin"])
            return

        args = message.text.split()[1:]
        if not args:
            await message.reply(self.S["warn"]["autoreset"]["usage"])
            return

        mode = args[0].lower()
        if mode not in ["on", "off"]:
            await message.reply(self.S["warn"]["autoreset"]["usage"])
            return
        
        enabled = mode == "on"
        autoreset_time = 0
        
        if enabled and len(args) > 1:
            time_value = parse_time(args[1])
            if time_value is None or time_value < 3600:  # minimum 1 hour
                await message.reply(self.S["warn"]["autoreset"]["min_time"])
                return
            autoreset_time = time_value
        
        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if not db_settings:
                return

            db_settings.warn_autoreset = enabled
            if enabled:
                db_settings.warn_autoreset_time = autoreset_time
            await session.commit()
        
        if enabled:
            if autoreset_time > 0:
                time_text = format_timedelta(timedelta(seconds=autoreset_time), locale=self.cur_lang, format='long')
                await message.reply(self.S["warn"]["autoreset"]["enabled_with_time"].format(time=time_text))
        else:
            await message.reply(self.S["warn"]["autoreset"]["disabled"])

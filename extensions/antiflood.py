from base.mod_ext import ModuleExtension
from base.module import command, allowed_for
from ..checks import restrict_check_message
from ..db import Antiflood
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from pyrogram.handlers import MessageHandler
from pyrogram.enums import ChatMemberStatus
from collections import deque as Deque, defaultdict
from datetime import datetime, timedelta
from sqlalchemy import select
from dataclasses import dataclass
from typing import Optional


@dataclass
class AntifloodCache:
    enabled: bool
    message_limit: int
    time_frame: int
    action: str
    action_duration: int


class AntiFloodExtension(ModuleExtension):
    def on_init(self):
        # In-memory storage: chat_id -> user_id -> {'deque': deque of (timestamp, identifier), 'identifiers': set}
        self.flood_data = defaultdict(lambda: defaultdict(lambda: {'deque': Deque(), 'identifiers': set()}))
        self.settings_cache: dict[int, Optional[AntifloodCache]] = {}

    @property
    def custom_handlers(self):
        return [
            (MessageHandler(self.antiflood_handler, filters.group), 1),
        ]

    async def antiflood_handler(self, bot: Client, message: Message):
        """Handle all incoming messages to detect flooding, treating albums as single units."""
        chat_id = message.chat.id

        if chat_id not in self.settings_cache:
            async with self.db.session_maker() as session:
                row = await session.scalar(select(Antiflood).filter_by(chat_id=chat_id))
                self.settings_cache[chat_id] = AntifloodCache(
                    enabled=row.enabled,
                    message_limit=row.message_limit,
                    time_frame=row.time_frame,
                    action=row.action,
                    action_duration=row.action_duration,
                ) if row else None

        settings = self.settings_cache.get(chat_id)
        if not settings or not settings.enabled:
            return

        if not message.from_user:
            return

        user_id = message.from_user.id
        current_time = message.date
        user_data = self.flood_data[chat_id][user_id]
        msg_deque = user_data['deque']
        identifiers = user_data['identifiers']

        while msg_deque and (current_time - msg_deque[0][0]).total_seconds() > settings.time_frame:
            _, old_identifier = msg_deque.popleft()
            identifiers.discard(old_identifier)

        identifier = message.media_group_id if message.media_group_id else message.id

        if identifier not in identifiers:
            msg_deque.append((current_time, identifier))
            identifiers.add(identifier)

        if len(msg_deque) > settings.message_limit:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                await self.take_antiflood_action(bot, message, settings)
                msg_deque.clear()
                identifiers.clear()

    async def take_antiflood_action(self, bot: Client, message: Message, settings: AntifloodCache):
        """Execute the configured action against the flooding user."""
        user = message.from_user
        action = settings.action
        name = f"@{user.username}" if user.username else user.first_name

        if action == "warn":
            warns_ext = next(
                (ext for ext in self._ModuleExtension__base_mod._BaseModule__extensions
                 if ext.__class__.__name__ == "WarnsExtension"), None
            )
            if warns_ext is None:
                self.logger.error("AntiFlood: WarnsExtension not found, cannot apply warn action.")
                return
            status = await warns_ext._warn_user(bot, message.chat.id, user.id, "Flooding")
            if status.get("error"):
                await message.reply(self.S["antiflood"]["warn_error"])
                return
            if status["limit_reached"]:
                await message.reply(self.S["antiflood"]["user_restricted"].format(name=name, restriction=status['restriction']))
            else:
                await message.reply(self.S["antiflood"]["user_warned"].format(name=name, warn_count=status['warn_count'], warn_limit=status['warn_limit']))
        elif action == "mute":
            duration = settings.action_duration
            until_date = (datetime.now() + timedelta(seconds=duration)) if duration > 0 else datetime.fromtimestamp(0)
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            await message.reply(self.S["antiflood"]["user_muted"].format(name=name))
        elif action == "ban":
            duration = settings.action_duration
            until_date = (datetime.now() + timedelta(seconds=duration)) if duration > 0 else datetime.fromtimestamp(0)
            await bot.ban_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                until_date=until_date
            )
            await message.reply(self.S["antiflood"]["user_banned"].format(name=name))

    @allowed_for(["chat_owner", "chat_admins"])
    @command("antiflood", filters.group)
    async def antiflood_cmd(self, bot: Client, message: Message):
        """Handle AntiFlood configuration commands."""
        args = message.text.split()
        if len(args) == 1:
            await self.show_antiflood_status(message)
        elif args[1] == "enable":
            await self.enable_antiflood(message)
        elif args[1] == "disable":
            await self.disable_antiflood(message)
        elif args[1] == "set":
            await self.set_antiflood(message)
        else:
            await message.reply(self.S["antiflood"]["invalid_subcommand"])

    def _cache_settings(self, chat_id: int, row: Antiflood) -> AntifloodCache:
        """Snapshot a settings row into the cache."""
        snapshot = AntifloodCache(
            enabled=row.enabled,
            message_limit=row.message_limit,
            time_frame=row.time_frame,
            action=row.action,
            action_duration=row.action_duration,
        )
        self.settings_cache[chat_id] = snapshot
        return snapshot

    async def show_antiflood_status(self, message: Message):
        """Display current AntiFlood settings."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(Antiflood).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply(self.S["antiflood"]["settings_not_found"])
                return
            status_text = self.S["antiflood"]["status"]["enabled"] if settings.enabled else self.S["antiflood"]["status"]["disabled"]
            action = settings.action
            action_details = action
            if action in ["mute", "ban"]:
                duration = settings.action_duration
                if duration > 0:
                    action_details = self.S["antiflood"]["status"]["action_duration"].format(action=action, duration=duration)
                else:
                    action_details = self.S["antiflood"]["status"]["action_permanent"].format(action=action)

            text = self.S["antiflood"]["status"]["info"].format(
                status=status_text,
                limit=settings.message_limit,
                time_frame=settings.time_frame,
                action_details=action_details
            )
            await message.reply(text)

    async def enable_antiflood(self, message: Message):
        """Enable AntiFlood for the chat."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(Antiflood).filter_by(chat_id=message.chat.id))
            if settings is None:
                # Auto-create row with defaults on first enable
                settings = Antiflood(chat_id=message.chat.id)
                session.add(settings)
            settings.enabled = True
            await session.commit()
            self._cache_settings(message.chat.id, settings)
        await message.reply(self.S["antiflood"]["enabled"])

    async def disable_antiflood(self, message: Message):
        """Disable AntiFlood for the chat."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(Antiflood).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply(self.S["antiflood"]["settings_not_found"])
                return
            settings.enabled = False
            await session.commit()
            self._cache_settings(message.chat.id, settings)
        await message.reply(self.S["antiflood"]["disabled"])

    async def set_antiflood(self, message: Message):
        """Set AntiFlood parameters."""
        args = message.text.split()
        if len(args) < 5:
            await message.reply(self.S["antiflood"]["set_usage"])
            return
        try:
            message_limit = int(args[2])
            time_frame = int(args[3])
            action = args[4].lower()
            if action not in ["warn", "mute", "ban"]:
                await message.reply(self.S["antiflood"]["invalid_action"])
                return
            duration = 0
            if action in ["mute", "ban"] and len(args) > 5:
                duration = int(args[5])
        except ValueError:
            await message.reply(self.S["antiflood"]["invalid_params"])
            return
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(Antiflood).filter_by(chat_id=message.chat.id))
            if settings is None:
                # Auto-create row with defaults, then apply the requested values
                settings = Antiflood(chat_id=message.chat.id)
                session.add(settings)
            settings.message_limit = message_limit
            settings.time_frame = time_frame
            settings.action = action
            settings.action_duration = duration
            await session.commit()
            self._cache_settings(message.chat.id, settings)
        await message.reply(self.S["antiflood"]["settings_updated"])

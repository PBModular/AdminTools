from base.mod_ext import ModuleExtension
from base.module import command, allowed_for
from ..checks import restrict_check_message
from ..db import ChatSettings
from ..extensions.warns import WarnsExtension
from pyrogram import Client, filters
from pyrogram.types import Message, ChatPermissions
from pyrogram.handlers import MessageHandler
from collections import deque, defaultdict
from datetime import datetime, timedelta
from sqlalchemy import select


class AntiFloodExtension(ModuleExtension):
    def on_init(self):
        # In-memory storage for message timestamps: chat_id -> user_id -> deque of timestamps
        self.flood_data = defaultdict(lambda: defaultdict(deque))
        self.settings_cache = {}
        self.bot.add_handler(MessageHandler(self.antiflood_handler, filters.group))

    async def antiflood_handler(self, bot: Client, message: Message):
        """Handle all incoming messages to detect flooding."""
        chat_id = message.chat.id

        # Load settings if not cached
        if chat_id not in self.settings_cache:
            async with self.db.session_maker() as session:
                settings = await session.scalar(select(ChatSettings).filter_by(chat_id=chat_id))
                self.settings_cache[chat_id] = settings

        settings = self.settings_cache.get(chat_id)
        if not settings or not settings.antiflood_enabled:
            return

        user_id = message.from_user.id
        current_time = message.date
        user_queue = self.flood_data[chat_id][user_id]

        while user_queue and (current_time - user_queue[0]).total_seconds() > settings.antiflood_time_frame:
            user_queue.popleft()

        user_queue.append(current_time)

        # Check for flooding
        if len(user_queue) > settings.antiflood_message_limit:
            member = await bot.get_chat_member(chat_id, user_id)
            if member.status not in {"administrator", "creator"}:
                await self.take_antiflood_action(bot, message, settings)
                user_queue.clear()  # Reset queue to prevent repeated actions

    async def take_antiflood_action(self, bot: Client, message: Message, settings):
        """Execute the configured action against the flooding user."""
        user = message.from_user
        action = settings.antiflood_action
        name = f"@{user.username}" if user.username else user.first_name

        if action == "warn":
            status = await WarnsExtension._warn_user(bot, message.chat.id, user.id, "Flooding")
            if status.get("error"):
                await message.reply(self.S["antiflood"]["warn_error"])
                return
            if status["limit_reached"]:
                await message.reply(self.S["antiflood"]["user_restricted"].format(name=name, restriction=status['restriction']))
            else:
                await message.reply(self.S["antiflood"]["user_warned"].format(name=name, warn_count=status['warn_count'], warn_limit=status['warn_limit']))
        elif action == "mute":
            duration = settings.antiflood_action_duration
            until_date = (datetime.now() + timedelta(seconds=duration)) if duration > 0 else datetime.fromtimestamp(0)
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            await message.reply(self.S["antiflood"]["user_muted"].format(name=name))
        elif action == "ban":
            duration = settings.antiflood_action_duration
            until_date = (datetime.now() + timedelta(seconds=duration)) if duration > 0 else datetime.fromtimestamp(0)
            await bot.ban_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                until_date=until_date
            )
            await message.reply(self.S["antiflood"]["user_banned"].format(name=name))

    @allowed_for(["chat_owner", "admins"])
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

    async def show_antiflood_status(self, message: Message):
        """Display current AntiFlood settings."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply(self.S["antiflood"]["settings_not_found"])
                return
            status_text = self.S["antiflood"]["status"]["enabled"] if settings.antiflood_enabled else self.S["antiflood"]["status"]["disabled"]
            action = settings.antiflood_action
            action_details = action
            if action in ["mute", "ban"]:
                duration = settings.antiflood_action_duration
                if duration > 0:
                    action_details = self.S["antiflood"]["status"]["action_duration"].format(action=action, duration=duration)
                else:
                    action_details = self.S["antiflood"]["status"]["action_permanent"].format(action=action)

            text = self.S["antiflood"]["status"]["info"].format(
                status=status_text,
                limit=settings.antiflood_message_limit,
                time_frame=settings.antiflood_time_frame,
                action_details=action_details
            )
            await message.reply(text)

    async def enable_antiflood(self, message: Message):
        """Enable AntiFlood for the chat."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply(self.S["antiflood"]["settings_not_found"])
                return
            settings.antiflood_enabled = True
            await session.commit()
            self.settings_cache[message.chat.id] = settings
        await message.reply(self.S["antiflood"]["enabled"])

    async def disable_antiflood(self, message: Message):
        """Disable AntiFlood for the chat."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply(self.S["antiflood"]["settings_not_found"])
                return
            settings.antiflood_enabled = False
            await session.commit()
            self.settings_cache[message.chat.id] = settings
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
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply(self.S["antiflood"]["settings_not_found"])
                return
            settings.antiflood_message_limit = message_limit
            settings.antiflood_time_frame = time_frame
            settings.antiflood_action = action
            settings.antiflood_action_duration = duration
            await session.commit()
            self.settings_cache[message.chat.id] = settings
        await message.reply(self.S["antiflood"]["settings_updated"])

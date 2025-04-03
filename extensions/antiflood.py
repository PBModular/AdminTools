from base.mod_ext import ModuleExtension
from base.module import command
from ..checks import restrict_check_message
from ..db import ChatSettings
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

        if action == "warn":
            await message.reply(f"{user.first_name}, please do not flood the chat.")
        elif action == "mute":
            duration = settings.antiflood_action_duration
            until_date = (datetime.now() + timedelta(seconds=duration)) if duration > 0 else datetime.fromtimestamp(0)
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date
            )
            await message.reply(f"{user.first_name} has been muted for flooding.")
        elif action == "ban":
            duration = settings.antiflood_action_duration
            until_date = (datetime.now() + timedelta(seconds=duration)) if duration > 0 else datetime.fromtimestamp(0)
            await bot.ban_chat_member(
                chat_id=message.chat.id,
                user_id=user.id,
                until_date=until_date
            )
            await message.reply(f"{user.first_name} has been banned for flooding.")

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
            await message.reply("Invalid subcommand. Use /antiflood [status|enable|disable|set]")

    async def show_antiflood_status(self, message: Message):
        """Display current AntiFlood settings."""
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply("Chat settings not found. Run /start AdminTools first.")
                return
            status = "enabled" if settings.antiflood_enabled else "disabled"
            action = settings.antiflood_action
            if action in ["mute", "ban"]:
                duration = settings.antiflood_action_duration
                action += f" for {duration} seconds" if duration > 0 else " permanently"
            text = f"AntiFlood is {status}.\n"
            text += f"Limit: {settings.antiflood_message_limit} messages in {settings.antiflood_time_frame} seconds.\n"
            text += f"Action: {action}"
            await message.reply(text)

    async def enable_antiflood(self, message: Message):
        """Enable AntiFlood for the chat."""
        if await restrict_check_message(self, message) is None:
            return
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply("Chat settings not found. Run /start AdminTools first.")
                return
            settings.antiflood_enabled = True
            await session.commit()
            self.settings_cache[message.chat.id] = settings
        await message.reply("AntiFlood has been enabled.")

    async def disable_antiflood(self, message: Message):
        """Disable AntiFlood for the chat."""
        if await restrict_check_message(self, message) is None:
            return
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply("Chat settings not found. Run /start AdminTools first.")
                return
            settings.antiflood_enabled = False
            await session.commit()
            self.settings_cache[message.chat.id] = settings
        await message.reply("AntiFlood has been disabled.")

    async def set_antiflood(self, message: Message):
        """Set AntiFlood parameters."""
        if await restrict_check_message(self, message) is None:
            return
        args = message.text.split()
        if len(args) < 5:
            await message.reply("Usage: /antiflood set <messages> <seconds> <action> [duration]")
            return
        try:
            message_limit = int(args[2])
            time_frame = int(args[3])
            action = args[4].lower()
            if action not in ["warn", "mute", "ban"]:
                await message.reply("Invalid action. Must be 'warn', 'mute', or 'ban'.")
                return
            duration = 0
            if action in ["mute", "ban"] and len(args) > 5:
                duration = int(args[5])
        except ValueError:
            await message.reply("Invalid parameters. Messages, seconds, and duration must be integers.")
            return
        async with self.db.session_maker() as session:
            settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if settings is None:
                await message.reply("Chat settings not found. Run /start AdminTools first.")
                return
            settings.antiflood_message_limit = message_limit
            settings.antiflood_time_frame = time_frame
            settings.antiflood_action = action
            settings.antiflood_action_duration = duration
            await session.commit()
            self.settings_cache[message.chat.id] = settings
        await message.reply("AntiFlood settings updated.")

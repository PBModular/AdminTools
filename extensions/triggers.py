from pyrogram import Client
from pyrogram import filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus, MessageMediaType

from sqlalchemy import select

from base.mod_ext import ModuleExtension
from base.module import command, message
from ..db import ChatSettings


class TriggersExtension(ModuleExtension):
    @message(filters.new_chat_members)
    async def greeting(self, _, message: Message):
        settings = self.db.session.scalar(select(ChatSettings).where(ChatSettings.chat_id == message.chat.id))
        if settings is None or not settings.greeting_enabled:
            return

        for user in message.new_chat_members:
            if user.is_bot:
                continue

            name = f"@{user.username}" if user.username else user.first_name
            if settings.greeting_file_id:
                await message.reply_cached_media(
                    file_id=settings.greeting_file_id,
                    caption=settings.greeting_text.format(
                        user=name, chat_title=message.chat.title, chat_username=message.chat.username,
                        default=self.S["greeting"]["default"].format(user=name, chat=message.chat.title)
                    ) if settings.greeting_text else None
                )
            else:
                await message.reply(settings.greeting_text.format(
                        user=name, chat_title=message.chat.title, chat_username=message.chat.username,
                        default=self.S["greeting"]["default"].format(user=name, chat=message.chat.title)
                ))

    @command("welcome", filters.group)
    async def switch_welcome_cmd(self, bot: Client, message: Message):
        settings = self.db.session.scalar(select(ChatSettings).where(ChatSettings.chat_id == message.chat.id))
        if settings is None:
            return

        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"])
            return

        args = message.text.split()
        if len(args) > 1:
            if args[1] not in ("on", "off", "yes", "no"):
                await message.reply(self.S["greeting"]["switch"]["illegal_usage"])
                return

            settings.greeting_enabled = True if args[1] in ("on", "yes") else False
        else:
            settings.greeting_enabled = not settings.greeting_enabled

        self.db.session.commit()

        await message.reply(
            self.S["greeting"]["switch"]["ok"].format(status=self.S["greeting"]["switch"][settings.greeting_enabled])
        )

    @command("setwelcome", filters.group)
    async def set_welcome_cmd(self, bot: Client, message: Message):
        settings = self.db.session.scalar(select(ChatSettings).where(ChatSettings.chat_id == message.chat.id))
        if settings is None:
            return

        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"])
            return

        text = None
        file_id = None
        if message.reply_to_message:
            msg = message.reply_to_message
        else:
            msg = message

        if msg.media is not None and not msg.media == MessageMediaType.WEB_PAGE:
            if msg.media in (
                    MessageMediaType.CONTACT, MessageMediaType.LOCATION, MessageMediaType.VENUE,
                    MessageMediaType.POLL, MessageMediaType.DICE, MessageMediaType.GAME
            ):
                await message.reply(self.S["greeting"]["set"]["unsupported_media"])
                return

            file_id = getattr(msg, msg.media.value).file_id
            if msg.caption is not None:
                if msg.caption.startswith("/setwelcome"):
                    args = msg.caption.html.split(maxsplit=1)
                    if len(args) > 1:
                        text = args[1]
                else:
                    text = msg.caption.html
        else:
            if msg.text.startswith("/setwelcome"):
                args = msg.text.html.split(maxsplit=1)
                if len(args) == 1:
                    await message.reply(self.S["greeting"]["set"]["illegal_usage"])
                    return

                text = args[1]
            else:
                text = msg.text.html

        settings.greeting_enabled = True
        settings.greeting_text = text
        settings.greeting_file_id = file_id
        self.db.session.commit()

        await message.reply(self.S["greeting"]["set"]["ok"])

    @command("resetwelcome", filters.group)
    async def reset_greeting_cmd(self, bot: Client, message: Message):
        settings = self.db.session.scalar(select(ChatSettings).where(ChatSettings.chat_id == message.chat.id))
        if settings is None:
            return

        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"])
            return

        settings.greeting_text = "{default}"
        settings.greeting_file_id = None
        self.db.session.commit()

        await message.reply(self.S["greeting"]["reset"])

from pyrogram.types import Message

from base.module import BaseModule
from base.mod_ext import ModuleExtension
from typing import Type

# Extensions
from .extensions.ban import BanExtension
from .extensions.mute import MuteExtension
from .extensions.purge import PurgeExtension
from .extensions.permissions import PermsExtension
from .extensions.warns import WarnsExtension
from .extensions.triggers import TriggersExtension
from .extensions.report import ReportExtension

# DB
from sqlalchemy import select
from .db import Base, ChatSettings

from .config import DefaultWarnSettings


class AdminModule(BaseModule):
    @property
    def module_extensions(self) -> list[Type[ModuleExtension]]:
        return [
            BanExtension,
            MuteExtension,
            PurgeExtension,
            PermsExtension,
            WarnsExtension,
            TriggersExtension,
            ReportExtension
        ]
    
    @property
    def db_meta(self):
        return Base.metadata

    async def start_cmd(self, _, message: Message):
        """Initialize database entry for chat"""
        async with self.db.session_maker() as session:
            db_settings = await session.scalar(select(ChatSettings).filter_by(chat_id=message.chat.id))
            if db_settings is not None:
                await message.reply(self.S["start"]["already"])
                return

            db_settings = ChatSettings(
                chat_id=message.chat.id,
                warn_limit=DefaultWarnSettings.limit,
                warn_restriction=DefaultWarnSettings.restriction,
                warn_rest_time=DefaultWarnSettings.time,
                greeting_text="{default}"
            )
            session.add(db_settings)
            await session.commit()

        await message.reply(self.S["start"]["ok"])

from base.mod_ext import ModuleExtension
from pyrogram import Client, filters
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio, InputMediaAnimation
from pyrogram.enums import ParseMode
from pyrogram.handlers import MessageHandler
from pyrogram.handlers.handler import Handler
from base.module import command, allowed_for
from ..db import Notes
from sqlalchemy import select, exc


class NotesExtension(ModuleExtension):
    def on_init(self):
        self.notes = {}

    @property
    def custom_handlers(self) -> list[Handler]:
        return [
            MessageHandler(self.handle_hashtag_note, filters.regex(r'^#[\w-]+$'))
        ]

    async def get_chat_notes(self, chat_id):
        async with self.db.session_maker() as session:
            result = await session.execute(select(Notes).where(Notes.chat_id == chat_id))
            notes = result.scalars().all()
        return notes

    async def set_chat_notes(self, chat_id, note_name, note_content, note_type):
        async with self.db.session_maker() as session:
            try:
                existing_note = await session.scalar(select(Notes).where(Notes.chat_id == chat_id, Notes.name == note_name))
                if existing_note:
                    existing_note.content = note_content
                    existing_note.type = note_type
                else:
                    new_note = Notes(chat_id=chat_id, name=note_name, content=note_content, type=note_type)
                    session.add(new_note)
                await session.commit()
            except exc.IntegrityError:
                await session.rollback()
                existing_note = await session.scalar(select(Notes).where(Notes.chat_id == chat_id, Notes.name == note_name))
                existing_note.content = note_content
                existing_note.type = note_type
                await session.commit()

    async def remove_chat_notes(self, chat_id, note_name):
        async with self.db.session_maker() as session:
            note_to_delete = await session.scalar(select(Notes).where(Notes.chat_id == chat_id, Notes.name == note_name))
            if note_to_delete:
                await session.delete(note_to_delete)
                await session.commit()
                return True
            else:
                return False

    @command("note")
    async def note_cmd(self, bot: Client, message: Message):
        try:
            note_name = message.text.split(" ", 1)[1]
        except IndexError:
            await message.reply(self.S["notes"]["specify_note_name"])
            return

        notes = await self.get_chat_notes(message.chat.id)
        note = next((note for note in notes if note.name == note_name), None)

        if not note:
            await message.reply(self.S["notes"]["note_not_found"])
            return
        
        await self.send_note(bot, message.chat.id, note)

    async def handle_hashtag_note(self, bot: Client, message: Message):
        if not message.text:
            return

        note_name = message.text[1:]
        notes = await self.get_chat_notes(message.chat.id)
        note = next((note for note in notes if note.name == note_name), None)

        if note:
            await self.send_note(bot, message.chat.id, note)

    async def send_note(self, bot: Client, chat_id, note):
        if note.type == "text":
            await bot.send_message(chat_id, note.content, parse_mode=ParseMode.MARKDOWN)
        elif note.type == "media":
            media_id, *caption = note.content.split("\n", 1)
            caption = caption[0] if caption else None
            await bot.send_cached_media(chat_id, media_id, caption=caption, parse_mode=ParseMode.MARKDOWN)
        elif note.type == "media_group":
            media_group = []
            media_files = note.content.strip().split("\n---\n")
            caption = ""
            for media_file in media_files:
                if ":" in media_file:
                    file_type, file_id = media_file.split(":", 1)
                    if file_type == "photo":
                        media_group.append(InputMediaPhoto(file_id))
                    elif file_type == "video":
                        media_group.append(InputMediaVideo(file_id))
                    elif file_type == "document":
                        media_group.append(InputMediaDocument(file_id))
                    elif file_type == "audio":
                        media_group.append(InputMediaAudio(file_id))
                    elif file_type == "animation":
                        media_group.append(InputMediaAnimation(file_id))
                else:
                    caption = media_file.strip()
            if media_group:
                media_group[-1].caption = caption
                media_group[-1].parse_mode = ParseMode.MARKDOWN
            await bot.send_media_group(chat_id, media_group)

    @command("notes")
    async def notes_cmd(self, bot: Client, message: Message):
        notes = await self.get_chat_notes(message.chat.id)
        chat_name = message.chat.title or message.chat.username
        if notes:
            sorted_notes = sorted(note.name for note in notes)
            notes_list = "\n".join([f"• <code>{note}</code>" for note in sorted_notes])
            await message.reply(self.S["notes"]["notes_list"].format(notes_list=notes_list, chat_name=chat_name))
        else:
            await message.reply(self.S["notes"]["no_notes"])

    @allowed_for(["chat_admins", "chat_owner"])
    @command("addnote")
    async def addnote_cmd(self, bot: Client, message: Message):
        if not message.reply_to_message:
            await message.reply(self.S["notes"]["reply_to_message"])
            return

        try:
            note_name = message.text.split(" ", 1)[1]
        except IndexError:
            await message.reply(self.S["notes"]["specify_note_name"])
            return

        if " " in note_name:
            await message.reply(self.S["notes"]["no_spaces"])
            return

        reply_message = message.reply_to_message

        if reply_message.text:
            note_content = reply_message.text.markdown
            note_type = "text"
        elif reply_message.media:
            if reply_message.media_group_id and not reply_message.caption:
                media = reply_message.photo or reply_message.video or reply_message.document or reply_message.audio or reply_message.animation
                if media:
                    note_content = media.file_id
                    note_type = "media"
                else:
                    await message.reply(self.S["notes"]["media_not_supported"])
                    return
            else:
                if reply_message.media_group_id:
                    media_group = await bot.get_media_group(reply_message.chat.id, reply_message.id)
                    note_content = ""
                    for media_message in media_group:
                        media = media_message.photo or media_message.video or media_message.document or media_message.audio or reply_message.animation
                        if media:
                            file_type = media.__class__.__name__.lower()
                            note_content += f"{file_type}:{media.file_id}\n---\n"
                    note_type = "media_group"
                else:
                    media = reply_message.photo or reply_message.video or reply_message.document or reply_message.audio or \
                        reply_message.voice or reply_message.animation or reply_message.sticker
                    note_content = media.file_id
                    note_type = "media"
                
                if reply_message.caption:
                    note_content += f"\n{reply_message.caption.markdown}"
        else:
            await message.reply(self.S["notes"]["media_not_supported"])
            return

        await self.set_chat_notes(message.chat.id, note_name, note_content, note_type)
        await message.reply(self.S["notes"]["note_added"].format(note_name=note_name))

    @allowed_for(["chat_admins", "chat_owner"])
    @command("rmnote")
    async def rmnote_cmd(self, bot: Client, message: Message):
        try:
            note_name = message.text.split(" ", 1)[1]
        except IndexError:
            await message.reply(self.S["notes"]["specify_note_name"])
            return
        
        note_removed = await self.remove_chat_notes(message.chat.id, note_name)
        if note_removed:
            await message.reply(self.S["notes"]["note_removed"].format(note_name=note_name))
        else:
            await message.reply(self.S["notes"]["note_not_found"])

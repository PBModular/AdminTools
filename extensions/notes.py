from base.mod_ext import ModuleExtension
from pyrogram import Client
from pyrogram.types import Message, InputMediaPhoto, InputMediaVideo, InputMediaDocument, InputMediaAudio
from pyrogram.enums import ParseMode
from base.module import command
from ..db import Notes
from sqlalchemy import select, exc


class NotesExtension(ModuleExtension):
    def on_init(self):
        self.notes = {}

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

    @command("note")
    async def note_cmd(self, bot: Client, message: Message):
        try:
            note_name = message.text.split(" ", 1)[1]
        except IndexError:
            await message.reply(self.S["notes"]["specify_note_name"])
            return

        notes = await self.get_chat_notes(message.chat.id)
        note = next((note for note in notes if note.name == note_name), None)

        if note:
            if note.type == "text":
                await bot.send_message(message.chat.id, note.content, parse_mode=ParseMode.MARKDOWN)
            elif note.type == "media":
                media_id, caption = note.content.split("\n", 1)
                await bot.send_cached_media(message.chat.id, media_id, caption=caption, parse_mode=ParseMode.MARKDOWN)
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
                    else:
                        caption = media_file.strip()
                media_group[-1].caption = caption
                media_group[-1].parse_mode = ParseMode.MARKDOWN
                await bot.send_media_group(message.chat.id, media_group)
        else:
            await message.reply(self.S["notes"]["note_not_found"])

    @command("notes")
    async def notes_cmd(self, bot: Client, message: Message):
        notes = await self.get_chat_notes(message.chat.id)
        if notes:
            notes_list = "\n".join([note.name for note in notes])
            await message.reply(self.S["notes"]["notes_list"].format(notes_list=notes_list))
        else:
            await message.reply(self.S["notes"]["no_notes"])

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

        reply_message = message.reply_to_message

        if reply_message.text:
            note_content = reply_message.text.markdown
            note_type = "text"
        elif reply_message.media:
            if reply_message.media_group_id:
                media_group = await bot.get_media_group(reply_message.chat.id, reply_message.id)
                note_content = ""
                for media_message in media_group:
                    media = media_message.photo or media_message.video or media_message.document or media_message.audio
                    if media:
                        file_type = media.__class__.__name__.lower()
                        note_content += f"{file_type}:{media.file_id}\n---\n"
                if reply_message.caption:
                    note_content += f"\n{reply_message.caption.markdown}"
                note_type = "media_group"
            else:
                media = reply_message.photo or reply_message.video or reply_message.document or reply_message.audio or \
                    reply_message.voice or reply_message.animation or reply_message.sticker
                note_content = f"{media.file_id}\n{reply_message.caption.markdown or ''}"
                note_type = "media"
        else:
            await message.reply(self.S["notes"]["media_not_supported"])
            return

        await self.set_chat_notes(message.chat.id, note_name, note_content, note_type)
        await message.reply(self.S["notes"]["note_added"].format(note_name=note_name))

    @command("rmnote")
    async def rmnote_cmd(self, bot: Client, message: Message):
        try:
            note_name = message.text.split(" ", 1)[1]
        except IndexError:
            await message.reply(self.S["notes"]["specify_note_name"])
            return
        
        await self.remove_chat_notes(message.chat.id, note_name)
        await message.reply(self.S["notes"]["note_removed"].format(note_name=note_name))

from base.mod_ext import ModuleExtension
from base.module import command
from ..utils import parse_user, UserParseStatus
from pyrogram import Client
from pyrogram import filters
from pyrogram.types import Message, ChatPrivileges, ChatMember
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors.exceptions.bad_request_400 import UserNotParticipant
from typing import Optional


class PermsExtension(ModuleExtension):
    async def checks(self, message: Message, restrict=False) -> Optional[ChatMember]:
        member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"], quote=True)
            return

        if member.status == ChatMemberStatus.ADMINISTRATOR and not member.privileges.can_promote_members:
            text = self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['promote_members']}</code>"
            if restrict and not member.privileges.can_restrict_members:
                text += f"\n- <code>{self.S['rights']['restrict_members']}</code>"
            await message.reply(text, quote=True)
            return

        me = await self.bot.get_me()
        me_member = await self.bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)

        err_text = ""
        if not me_member.status == ChatMemberStatus.ADMINISTRATOR or not me_member.privileges.can_restrict_members:
            err_text += self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['restrict_members']}</code>\n"

        if not me_member.status == ChatMemberStatus.ADMINISTRATOR or not me_member.privileges.can_promote_members:
            err_text += self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['promote_members']}</code>"

        if err_text != "":
            await message.reply(err_text, quote=True)
            return

        status, user = await parse_user(self.bot, message)
        if status == UserParseStatus.INVALID_MENTION:
            await message.reply(self.S["user_not_found"], quote=True)
            return

        if status == UserParseStatus.NO_REPLY:
            await message.reply(self.S["no_reply"], quote=True)
            return

        me = await self.bot.get_me()
        if user.id == me.id or user.id == message.from_user.id:
            await message.reply(self.S["nice_try"], quote=True)
            return

        try:
            affect_member = await self.bot.get_chat_member(
                chat_id=message.chat.id, user_id=user.id
            )
        except UserNotParticipant:
            await message.reply(self.S["user_not_found"], quote=True)
            return

        return affect_member

    @command("promote", filters.group)
    async def promote_cmd(self, bot: Client, message: Message):
        affect_member = await self.checks(message, restrict=True)
        if affect_member is None:
            return

        if affect_member.status == ChatMemberStatus.ADMINISTRATOR or affect_member.status == ChatMemberStatus.OWNER:
            await message.reply(self.S["already_admin"], quote=True)
            return

        _, user = await parse_user(bot, message)

        name = f"@{user.username}" if user.username else user.first_name
        await bot.promote_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            privileges=ChatPrivileges(
                can_delete_messages=True,
                can_manage_video_chats=True,
                can_restrict_members=True,
                can_change_info=True,
                can_invite_users=True,
                can_pin_messages=True
            )
        )
        await message.reply(self.S["promote"].format(user=name))

    @command("demote", filters.group)
    async def demote_cmd(self, bot: Client, message: Message):
        affect_member = await self.checks(message, restrict=True)
        if affect_member is None:
            return

        if affect_member.status == ChatMemberStatus.OWNER:
            await message.reply(self.S["nice_try"], quote=True)
            return

        if not affect_member.status == ChatMemberStatus.ADMINISTRATOR:
            await message.reply(self.S["typical_user"], quote=True)
            return

        if not affect_member.can_be_edited:
            await message.reply(self.S["demote"]["err"], quote=True)
            return

        _, user = await parse_user(bot, message)
        name = f"@{user.username}" if user.username else user.first_name

        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=user.id,
            permissions=message.chat.permissions
        )
        await message.reply(self.S["demote"]["ok"].format(user=name))

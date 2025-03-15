from base.mod_ext import ModuleExtension
from base.module import command
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ChatMemberStatus
from asyncio import sleep


class PurgeExtension(ModuleExtension):
    @command("purge", filters.group)
    async def purge_cmd(self, bot: Client, message: Message):
        member = await bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        if not (member.status == ChatMemberStatus.ADMINISTRATOR or member.status == ChatMemberStatus.OWNER):
            await message.reply(self.S["not_admin"])
            return

        if not member.privileges.can_delete_messages:
            await message.reply(self.S["user_insufficient_rights"] + f"- <code>{self.S['rights']['delete_messages']}</code>")
            return

        me = await bot.get_me()
        me_member = await bot.get_chat_member(chat_id=message.chat.id, user_id=me.id)

        if message.reply_to_message is None:
            await message.reply(self.S["no_reply"])
            return

        if not me_member.privileges.can_delete_messages:
            await message.reply(
                self.S["bot_insufficient_rights"] + f"- <code>{self.S['rights']['delete_messages']}</code>"
            )
            return

        msg_count = message.id - message.reply_to_message.id
        count = 0
        while msg_count > 0:
            count += await bot.delete_messages(
                chat_id=message.chat.id,
                message_ids=range(message.id - msg_count, message.id + 1)
            )
            msg_count -= 100

        msg = await message.reply(text=self.S["purge"].format(count=count))
        await sleep(4)
        await msg.delete()

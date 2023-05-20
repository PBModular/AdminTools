from base.mod_ext import ModuleExtension
from base.module import command
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
import time


class ReportExtension(ModuleExtension):
    report_cooldown = 60
    
    def __init__(self, module):
        super().__init__(module)
        self.last_report_times = {}
    
    @command("report")
    async def report_cmd(self, bot: Client, message: Message):
        if message.reply_to_message is None:
            await message.reply(self.S["report"]["not_reply"])
            return
        
        chat_id = message.chat.id
        user_id = message.from_user.id
        reply_user_id = message.reply_to_message.from_user.id
        is_bot = message.reply_to_message.from_user.is_bot
        
        reply_member = await bot.get_chat_member(chat_id=chat_id, user_id=reply_user_id)
        if reply_member.status == ChatMemberStatus.ADMINISTRATOR and not is_bot or reply_member.status == ChatMemberStatus.OWNER:
            await message.reply(self.S["report"]["admin"])
            return

        if user_id == reply_user_id:
            await message.reply(self.S["report"]["yourself"])
            return
        
        if is_bot:
            await message.reply(self.S["report"]["bot"])
            return
        
        if chat_id in self.last_report_times:
            last_report_time = self.last_report_times[chat_id].get(user_id, 0)
            current_time = time.time()
            
            if current_time - last_report_time < self.report_cooldown:
                cooldown_time = self.report_cooldown - int(current_time - last_report_time)
                await message.reply(self.S["report"]["cooldown"].format(cooldown_time=cooldown_time))
                return

        self.last_report_times.setdefault(chat_id, {})[user_id] = time.time()

        chat_title = message.chat.title or message.chat.username or message.chat.first_name
        user = message.from_user.mention
        reported_msg = message.reply_to_message_id
        reported_user = message.reply_to_message.from_user.mention
        reported_text = message.reply_to_message.text
        
        button_url = f"https://t.me/c/{str(chat_id)[4:]}/{reported_msg}"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(self.S["report"]["msg"], url=button_url)]
        ])

        async for admin in bot.get_chat_members(chat_id, filter=ChatMembersFilter.ADMINISTRATORS):
            try:
                if admin.user.is_bot:
                    continue
                
                await bot.send_message(
                    admin.user.id,
                    self.S["report"]["alert"].format(
                        chat_title=chat_title,
                        user=user,
                        reported_user=reported_user,
                        reported_text=reported_text
                    ),
                    reply_markup=keyboard
                )
                
            except Exception as e:
                # self.logger.warning(f"Failed to send report to {admin.user.id}: {e}")
                continue
        
        await message.reply(self.S["report"]["sent"])

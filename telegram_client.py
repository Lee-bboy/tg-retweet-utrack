import asyncio
import json
from typing import Optional, Dict, Any
from telegram import Bot
from telegram.error import TelegramError
from loguru import logger
import config

class TelegramClient:
    """Telegram客户端，用于发送消息到Telegram"""
    
    def __init__(self):
        self.bot = Bot(token=config.config.TELEGRAM_BOT_TOKEN)
        self.chat_id = config.config.TELEGRAM_CHAT_ID
        self.message_queue = asyncio.Queue()
        self.is_running = False
        
    async def start(self):
        """启动Telegram客户端"""
        if not config.config.TELEGRAM_BOT_TOKEN or not config.config.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 必须配置")
        
        self.is_running = True
        logger.info("Telegram客户端已启动")
        
        # 启动消息处理器
        asyncio.create_task(self._message_processor())
        
    async def stop(self):
        """停止Telegram客户端"""
        self.is_running = False
        logger.info("Telegram客户端已停止")
        
    async def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """发送消息到Telegram"""
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=False
            )
            logger.info(f"消息已发送到Telegram: {text[:100]}...")
            return True
        except TelegramError as e:
            logger.error(f"发送Telegram消息失败: {e}")
            return False
        except Exception as e:
            logger.error(f"发送Telegram消息时发生未知错误: {e}")
            return False
            
    async def send_photo(self, photo_url: str, caption: str = "", parse_mode: str = "HTML") -> bool:
        """发送图片到Telegram"""
        try:
            await self.bot.send_photo(
                chat_id=self.chat_id,
                photo=photo_url,
                caption=caption,
                parse_mode=parse_mode
            )
            logger.info(f"图片已发送到Telegram: {caption[:100]}...")
            return True
        except TelegramError as e:
            logger.error(f"发送Telegram图片失败: {e}")
            return False
        except Exception as e:
            logger.error(f"发送Telegram图片时发生未知错误: {e}")
            return False
            
    async def send_media_group(self, media_items: list) -> bool:
        """发送媒体组到Telegram"""
        try:
            await self.bot.send_media_group(
                chat_id=self.chat_id,
                media=media_items
            )
            logger.info("媒体组已发送到Telegram")
            return True
        except TelegramError as e:
            logger.error(f"发送Telegram媒体组失败: {e}")
            return False
        except Exception as e:
            logger.error(f"发送Telegram媒体组时发生未知错误: {e}")
            return False
            
    async def queue_message(self, message_data: Dict[str, Any]):
        """将消息加入队列"""
        await self.message_queue.put(message_data)
        
    async def _message_processor(self):
        """消息处理器"""
        while self.is_running:
            try:
                # 立即处理消息，不等待批次
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=0.1  # 100ms超时，更快响应
                    )
                    await self._process_message_batch([message])
                except asyncio.TimeoutError:
                    # 超时后继续循环
                    continue
                    
            except Exception as e:
                logger.error(f"消息处理器错误: {e}")
                await asyncio.sleep(0.1)  # 100ms错误恢复间隔
                
    async def _process_message_batch(self, messages: list):
        """处理消息批次"""
        for message_data in messages:
            try:
                message_type = message_data.get("type", "text")
                
                if message_type == "text":
                    await self.send_message(message_data["text"])
                elif message_type == "photo":
                    await self.send_photo(
                        message_data["photo_url"],
                        message_data.get("caption", "")
                    )
                elif message_type == "media_group":
                    await self.send_media_group(message_data["media_items"])
                    
            except Exception as e:
                logger.error(f"处理消息时发生错误: {e}")
                
    async def test_connection(self) -> bool:
        """测试Telegram连接"""
        try:
            me = await self.bot.get_me()
            logger.info(f"Telegram Bot连接成功: @{me.username}")
            return True
        except Exception as e:
            logger.error(f"Telegram Bot连接失败: {e}")
            return False 
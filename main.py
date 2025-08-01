#!/usr/bin/env python3
"""
Twitter推文转发到Telegram的主程序
"""

import asyncio
import signal
import sys
import os
from pathlib import Path
from loguru import logger
import config
from websocket_client import WebSocketClient

class TelegramForwarder:
    """Telegram转发器主类"""
    
    def __init__(self):
        self.websocket_client = WebSocketClient()
        self.is_running = False
        
    async def start(self):
        """启动转发器"""
        try:
            # 设置日志
            self._setup_logging()
            
            # 检查配置
            self._validate_config()
            
            # 设置信号处理
            self._setup_signal_handlers()
            
            logger.info("🚀 启动Twitter推文转发到Telegram服务")
            logger.info(f"📡 WebSocket URL: {config.config.WSS_URL}")
            logger.info(f"📱 Telegram Chat ID: {config.config.TELEGRAM_CHAT_ID}")
            
            self.is_running = True
            
            # 启动WebSocket客户端
            await self.websocket_client.start()
            
        except Exception as e:
            logger.error(f"启动失败: {e}")
            sys.exit(1)
            
    async def stop(self):
        """停止转发器"""
        logger.info("🛑 正在停止服务...")
        self.is_running = False
        
        if self.websocket_client:
            await self.websocket_client.stop()
            
        logger.info("✅ 服务已停止")
        
    def _setup_logging(self):
        """设置日志配置"""
        # 创建日志目录
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # 移除默认处理器
        logger.remove()
        
        # 添加控制台处理器
        logger.add(
            sys.stdout,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=config.config.LOG_LEVEL,
            colorize=True
        )
        
        # 添加文件处理器
        logger.add(
            config.config.LOG_FILE,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=config.config.LOG_LEVEL,
            rotation="10 MB",
            retention="7 days",
            compression="gz"
        )
        
    def _validate_config(self):
        """验证配置"""
        if not config.config.TELEGRAM_BOT_TOKEN:
            raise ValueError("TELEGRAM_BOT_TOKEN 未配置")
            
        if not config.config.TELEGRAM_CHAT_ID:
            raise ValueError("TELEGRAM_CHAT_ID 未配置")
            
        if not config.config.WSS_URL:
            raise ValueError("WSS_URL 未配置")
            
        logger.info("✅ 配置验证通过")
        
    def _setup_signal_handlers(self):
        """设置信号处理器"""
        def signal_handler(signum, frame):
            logger.info(f"收到信号 {signum}，准备停止服务")
            asyncio.create_task(self.stop())
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def run(self):
        """运行转发器"""
        try:
            await self.start()
            
            # 保持运行
            while self.is_running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("收到中断信号")
        except Exception as e:
            logger.error(f"运行时错误: {e}")
        finally:
            await self.stop()

async def main():
    """主函数"""
    forwarder = TelegramForwarder()
    await forwarder.run()

if __name__ == "__main__":
    # 设置事件循环策略（Windows兼容性）
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    # 运行主程序
    asyncio.run(main()) 
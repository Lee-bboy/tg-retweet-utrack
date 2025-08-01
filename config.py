import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config(BaseSettings):
    """配置类"""
    
    # WebSocket配置
    WSS_URL: str = "wss://api.utrack.club/ws?token=78tCbNuZmZ2Rxi5C2xcUN8MQYqsihSBf"
    
    # Telegram Bot配置
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    
    # 连接配置
    RECONNECT_INTERVAL: int = 100  # 100ms重连间隔，更快重连
    MAX_RECONNECT_ATTEMPTS: int = 99999
    HEARTBEAT_INTERVAL: int = 100  # 100ms心跳，更频繁
    CONNECTION_TIMEOUT: int = 500  # 500ms连接超时，更快检测
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/telegram_forwarder.log"
    
    # 消息处理配置
    MAX_MESSAGE_LENGTH: int = 4096  # Telegram消息最大长度
    BATCH_SIZE: int = 10  # 批处理大小
    
    # 性能监控
    ENABLE_PERFORMANCE_MONITORING: bool = True
    LATENCY_THRESHOLD_MS: int = 1000  # 延迟阈值
    
    class Settings:
        env_file = ".env"
        env_file_encoding = "utf-8"

# 创建全局配置实例
config = Config()

# 如果环境变量存在，覆盖默认值
if os.getenv("TELEGRAM_BOT_TOKEN"):
    config.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if os.getenv("TELEGRAM_CHAT_ID"):
    config.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") 
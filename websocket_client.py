import asyncio
import json
import time
from typing import Optional, Dict, Any
from websockets import connect, WebSocketServerProtocol
from websockets.exceptions import ConnectionClosed, WebSocketException
from loguru import logger
import config
from telegram_client import TelegramClient
from message_processor import MessageProcessor
from datetime import datetime

class WebSocketClient:
    """WebSocket客户端，用于连接Twitter数据源"""
    
    def __init__(self):
        self.websocket: Optional[WebSocketServerProtocol] = None
        self.telegram_client = TelegramClient()
        self.message_processor = MessageProcessor()
        self.is_running = False
        self.reconnect_attempts = 0
        self.last_heartbeat = time.time()
        self.connection_start_time = None
        self.message_count = 0
        self.error_count = 0
        
    async def start(self):
        """启动WebSocket客户端"""
        self.is_running = True
        
        # 启动Telegram客户端
        await self.telegram_client.start()
        
        # 测试Telegram连接
        if not await self.telegram_client.test_connection():
            logger.error("Telegram连接失败，请检查配置")
            return
            
        logger.info("WebSocket客户端启动")
        
        # 开始连接循环
        while self.is_running:
            try:
                await self._connect()
            except Exception as e:
                logger.error(f"连接失败: {e}")
                await self._handle_connection_failure(str(e))
                
    async def stop(self):
        """停止WebSocket客户端"""
        self.is_running = False
        
        if self.websocket:
            await self.websocket.close()
            
        await self.telegram_client.stop()
        logger.info("WebSocket客户端已停止")
        
    async def _connect(self):
        """建立WebSocket连接"""
        try:
            logger.info(f"正在连接到 {config.config.WSS_URL}")
            
            # 优化WebSocket连接配置，减少延迟
            self.websocket = await connect(
                config.config.WSS_URL,
                ping_interval=100,  # 100ms ping间隔，更频繁的心跳
                ping_timeout=50,    # 50ms ping超时，更快检测连接问题
                close_timeout=3,    # 3秒关闭超时
                max_size=1024*1024, # 1MB最大消息大小
                compression=None,    # 禁用压缩减少延迟
                max_queue=32,       # 限制队列大小
                read_limit=2**16,   # 读取限制
                write_limit=2**16   # 写入限制
            )
            
            self.connection_start_time = time.time()
            self.reconnect_attempts = 0
            self.last_heartbeat = time.time()
            
            logger.info("WebSocket连接成功")
            
            # 开始消息处理循环
            await self._message_loop()
            
        except Exception as e:
            logger.error(f"WebSocket连接失败: {e}")
            raise
            
    async def _message_loop(self):
        """消息处理循环"""
        try:
            async for message in self.websocket:
                if not self.is_running:
                    break
                    
                await self._handle_message(message)
                
        except ConnectionClosed:
            logger.warning("WebSocket连接已关闭")
        except WebSocketException as e:
            logger.error(f"WebSocket异常: {e}")
        except Exception as e:
            logger.error(f"消息处理异常: {e}")
            
    async def _handle_message(self, message: str):
        """处理接收到的消息"""
        try:
            # 获取高精度时间戳
            receive_time = time.time()
            receive_time_ms = int(receive_time * 1000)
            receive_time_str = datetime.fromtimestamp(receive_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            self.message_count += 1
            
            # 记录原始消息接收（包含毫秒精度时间）
            logger.info(f"📨 [原始数据] 收到WebSocket消息: {message}")
            logger.info(f"⏰ [接收时间] 时间戳: {receive_time_ms}ms")
            logger.info(f"⏰ [接收时间] 日期格式: {receive_time_str}")
            
            # 检查是否为Twitter消息
            is_twitter = self.message_processor.is_twitter_message(message)
            
            # 解析消息
            parsed_data = self.message_processor.parse_message(message)
            if not parsed_data:
                logger.warning("无法解析消息")
                return
                
            # 记录推文发布时间和延迟计算（如果是推文消息）
            if parsed_data.get('type') == 'utrack_tweet':
                original_created_at = parsed_data.get('created_at', '')
                logger.info(f"📅 [推文时间] 原始发布时间: {original_created_at}")
                
                # 计算延迟
                if original_created_at:
                    try:
                        # 解析推文发布时间
                        tweet_timestamp = None
                        if isinstance(original_created_at, (int, str)):
                            try:
                                timestamp = int(original_created_at)
                                if timestamp > 1000000000000:  # 毫秒时间戳
                                    timestamp = timestamp / 1000
                                tweet_timestamp = timestamp
                            except ValueError:
                                pass
                        
                        if tweet_timestamp:
                            # 计算延迟（毫秒）
                            delay_ms = int((receive_time - tweet_timestamp) * 1000)
                            logger.info(f"🚀 [延迟监控] 推文发布到接收延迟: {delay_ms}ms")
                            
                            # 延迟警告
                            if delay_ms > 1000:
                                logger.warning(f"⚠️ [延迟警告] 延迟过高: {delay_ms}ms (>1秒)")
                            elif delay_ms > 500:
                                logger.warning(f"⚠️ [延迟警告] 延迟较高: {delay_ms}ms (>500ms)")
                            else:
                                logger.info(f"✅ [延迟监控] 延迟正常: {delay_ms}ms")
                        
                        # 尝试解析时间并记录
                        parsed_time = self.message_processor._parse_time(str(original_created_at))
                        if parsed_time:
                            logger.info(f"📅 [推文时间] 解析后时间: {parsed_time}")
                        else:
                            logger.warning(f"📅 [推文时间] 无法解析时间格式: {original_created_at}")
                    except Exception as e:
                        logger.error(f"📅 [推文时间] 时间解析错误: {e}")
            
            # 格式化Telegram消息
            telegram_message = self.message_processor.format_telegram_message(parsed_data)
            if not telegram_message:
                logger.warning("无法格式化Telegram消息")
                return
                
            # 发送到Telegram
            await self.telegram_client.queue_message(telegram_message)
            
            # 计算处理时间
            processing_time = (time.time() - receive_time) * 1000
            
            # 记录性能统计
            if is_twitter:
                logger.info(f"🐦 [Twitter消息] 处理完成 - 耗时: {processing_time:.2f}ms")
            else:
                logger.debug(f"💬 [普通消息] 处理完成 - 耗时: {processing_time:.2f}ms")
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"处理消息时发生错误: {e}")
            
    async def _handle_connection_failure(self, reason: str):
        """处理连接失败"""
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > config.config.MAX_RECONNECT_ATTEMPTS:
            logger.error(f"重连次数超过限制 ({config.config.MAX_RECONNECT_ATTEMPTS})，停止重连")
            self.is_running = False
            return
            
        # 计算重连延迟（更激进的策略）
        delay = min(
            config.config.RECONNECT_INTERVAL * (1.01 ** min(self.reconnect_attempts, 5)),  # 更小的退避倍数
            2000  # 最大2秒延迟
        )
        
        logger.warning(f"连接失败: {reason}")
        logger.info(f"将在 {delay/1000:.1f} 秒后重连 (尝试 {self.reconnect_attempts}/{config.config.MAX_RECONNECT_ATTEMPTS})")
        
        await asyncio.sleep(delay / 1000)
                
    async def send_heartbeat(self):
        """发送心跳"""
        if self.websocket and self.is_running:
            try:
                heartbeat_msg = {
                    "type": "ping",
                    "timestamp": time.time()
                }
                await self.websocket.send(json.dumps(heartbeat_msg))
                self.last_heartbeat = time.time()
                logger.debug("心跳已发送")
            except Exception as e:
                logger.error(f"发送心跳失败: {e}")
                
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        uptime = time.time() - (self.connection_start_time or time.time())
        
        return {
            "uptime_seconds": uptime,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "reconnect_attempts": self.reconnect_attempts,
            "is_connected": self.websocket is not None and not self.websocket.closed,
            "last_heartbeat": self.last_heartbeat
        }
        
    async def start_heartbeat_loop(self):
        """启动心跳循环"""
        while self.is_running:
            try:
                await asyncio.sleep(config.config.HEARTBEAT_INTERVAL / 1000)
                if self.is_running:
                    await self.send_heartbeat()
            except Exception as e:
                logger.error(f"心跳循环错误: {e}")
                
    async def start_stats_monitor(self):
        """启动统计监控"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # 每分钟输出一次统计
                if self.is_running:
                    stats = self.get_stats()
                    logger.info(f"统计信息: {stats}")
            except Exception as e:
                logger.error(f"统计监控错误: {e}") 
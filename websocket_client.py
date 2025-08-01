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
            
            # 超低延迟WebSocket连接配置
            self.websocket = await connect(
                config.config.WSS_URL,
                ping_interval=20,     # 20ms ping间隔，极频繁心跳
                ping_timeout=10,      # 10ms ping超时，极快检测
                close_timeout=0.5,    # 0.5秒关闭超时
                max_size=256*1024,    # 256KB最大消息大小，进一步减少内存占用
                compression=None,      # 禁用压缩减少延迟
                max_queue=8,          # 更小队列，减少缓冲
                read_limit=2**13,     # 更小读取限制，更快处理
                write_limit=2**13,    # 更小写入限制，更快发送
                extra_headers={        # 添加性能优化头部
                    'Connection': 'keep-alive',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Accept-Encoding': 'identity'  # 禁用压缩
                }
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
        """超低延迟消息处理循环"""
        try:
            # 使用更高效的消息监听方式
            while self.is_running and not self.websocket.closed:
                try:
                    # 使用超短超时，立即处理消息
                    message = await asyncio.wait_for(
                        self.websocket.recv(),
                        timeout=0.01  # 10ms超时，极快响应
                    )
                    
                    if message:
                        # 立即处理消息，不等待
                        asyncio.create_task(self._handle_message(message))
                        
                except asyncio.TimeoutError:
                    # 超时继续循环，不记录日志减少开销
                    continue
                except ConnectionClosed:
                    logger.warning("WebSocket连接已关闭")
                    break
                except WebSocketException as e:
                    logger.error(f"WebSocket异常: {e}")
                    break
                except Exception as e:
                    logger.error(f"消息处理异常: {e}")
                    # 短暂暂停后继续
                    await asyncio.sleep(0.001)
                    
        except Exception as e:
            logger.error(f"消息循环异常: {e}")
            
    async def _handle_message(self, message: str):
        """超低延迟消息处理"""
        try:
            # 获取高精度时间戳
            receive_time = time.time()
            receive_time_ms = int(receive_time * 1000)
            receive_time_str = datetime.fromtimestamp(receive_time).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            self.message_count += 1
            
            # 记录接收时间日志
            logger.info(f"📨 [接收时间] 时间戳: {receive_time_ms}ms")
            logger.info(f"📨 [接收时间] 格式化: {receive_time_str}")
            
            # 快速检查是否为Twitter消息
            is_twitter = self.message_processor.is_twitter_message(message)
            
            # 解析消息
            parsed_data = self.message_processor.parse_message(message)
            if not parsed_data:
                return
                
            # 推文发布时间处理（仅对Twitter消息）
            if is_twitter and parsed_data.get('type') == 'utrack_tweet':
                original_created_at = parsed_data.get('created_at', '')
                if original_created_at:
                    try:
                        # 记录推文发布时间
                        logger.info(f"📅 [推文时间] 原始发布时间: {original_created_at}")
                        
                        # 快速时间戳解析
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
                            # 记录解析后的推文时间
                            tweet_time_str = datetime.fromtimestamp(tweet_timestamp).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                            logger.info(f"📅 [推文时间] 解析后时间: {tweet_time_str}")
                            
                            # 计算延迟（毫秒）
                            delay_ms = int((receive_time - tweet_timestamp) * 1000)
                            logger.info(f"🚀 [延迟监控] 推文发布到接收延迟: {delay_ms}ms")
                            
                            # 延迟警告
                            if delay_ms > 800:
                                logger.warning(f"⚠️ [延迟警告] 延迟过高: {delay_ms}ms")
                            elif delay_ms > 500:
                                logger.warning(f"⚠️ [延迟警告] 延迟较高: {delay_ms}ms")
                            else:
                                logger.info(f"✅ [延迟监控] 延迟正常: {delay_ms}ms")
                            
                    except Exception as e:
                        logger.error(f"📅 [推文时间] 时间解析错误: {e}")
            
            # 格式化Telegram消息
            telegram_message = self.message_processor.format_telegram_message(parsed_data)
            if not telegram_message:
                return
                
            # 立即发送到Telegram（不等待）
            asyncio.create_task(self.telegram_client.queue_message(telegram_message))
            
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
            
        # 超快重连策略
        delay = min(
            config.config.RECONNECT_INTERVAL * (1.005 ** min(self.reconnect_attempts, 3)),  # 极小的退避倍数
            1000  # 最大1秒延迟
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
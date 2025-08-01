import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from loguru import logger
import config

class MessageProcessor:
    """消息处理器，用于解析和格式化UTrack WebSocket消息"""
    
    def __init__(self):
        self.twitter_url_patterns = [
            r'https?://(?:www\.)?twitter\.com',
            r'https?://(?:www\.)?t\.co',
            r'https?://(?:www\.)?x\.com'
        ]
        
    def is_twitter_message(self, message_content: str) -> bool:
        """检查是否为Twitter消息"""
        if not message_content:
            return False
            
        # 检查是否包含Twitter URL
        for pattern in self.twitter_url_patterns:
            if re.search(pattern, message_content, re.IGNORECASE):
                return True
                
        # 检查消息结构
        try:
            data = json.loads(message_content)
            if isinstance(data, dict):
                # 检查是否包含推文相关字段
                tweet_fields = ['tweet', 'twitter', 'text', 'user', 'created_at']
                if any(field in str(data).lower() for field in tweet_fields):
                    return True
        except (json.JSONDecodeError, TypeError):
            pass
            
        return False
        
    def extract_contract_info(self, text: str) -> List[str]:
        """提取智能合约信息"""
        contract_info = []
        
        if not text:
            return contract_info
        
        # Solana地址模式 (base58, 32-44字符)
        solana_pattern = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
        solana_matches = re.findall(solana_pattern, text)
        
        if solana_matches:
            for address in solana_matches:
                # 简单验证：Solana地址通常以特定字符开头
                if len(address) >= 32 and len(address) <= 44:
                    contract_info.append(f"🟣 Solana: `{address}`")
        
        # Ethereum地址模式 (0x开头，40个十六进制字符)
        eth_pattern = r'0x[a-fA-F0-9]{40}'
        eth_matches = re.findall(eth_pattern, text)
        
        if eth_matches:
            for address in eth_matches:
                contract_info.append(f"🔷 Ethereum: `{address}`")
        
        # 常见加密货币关键词
        crypto_keywords = [
            '$BTC', '$ETH', '$SOL', '$USDT', '$USDC', 
            'CA:', 'Contract:', 'DeFi', 'NFT', 'Token',
            'CA =', 'Contract Address', 'Smart Contract',
            'Token Address', 'Contract Addr'
        ]
        
        found_keywords = []
        for keyword in crypto_keywords:
            if keyword.upper() in text.upper():
                found_keywords.append(keyword)
        
        if found_keywords:
            contract_info.append(f"🏷️ 关键词: {', '.join(found_keywords)}")
        
        return contract_info
        
    def parse_message(self, raw_message: str) -> Optional[Dict[str, Any]]:
        """解析原始消息"""
        try:
            logger.info(f"🔍 [解析开始] 开始解析消息: {raw_message[:200]}...")
            
            # 尝试解析JSON
            if raw_message.startswith('{') or raw_message.startswith('['):
                data = json.loads(raw_message)
                logger.info(f"✅ [JSON解析] 成功解析JSON数据")
                result = self._parse_json_message(data)
                logger.info(f"📊 [解析结果] 消息类型: {result.get('type', 'unknown')}")
                return result
            else:
                logger.info(f"📝 [文本解析] 按文本消息处理")
                return self._parse_text_message(raw_message)
        except json.JSONDecodeError as e:
            logger.error(f"❌ [JSON错误] JSON解析失败: {e}")
            return self._parse_text_message(raw_message)
        except Exception as e:
            logger.error(f"❌ [解析错误] 解析消息失败: {e}")
            return None
            
    def _parse_json_message(self, data: Any) -> Optional[Dict[str, Any]]:
        """解析JSON格式消息"""
        if isinstance(data, dict):
            # 检查是否为UTrack推文消息
            if 'tweet' in data and 'type' in data:
                return self._parse_utrack_tweet_message(data)
            # 检查是否为关注消息
            elif 'user' in data and 'type' in data:
                return self._parse_utrack_following_message(data)
            # 检查是否为用户资料更新消息
            elif 'profile' in data and 'type' in data and data.get('type') == 'profile.update':
                return self._parse_utrack_profile_update_message(data)
            else:
                # 通用消息格式
                return {
                    'type': 'text',
                    'content': json.dumps(data, ensure_ascii=False, indent=2),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'websocket'
                }
        elif isinstance(data, list):
            # 处理消息列表
            messages = []
            for item in data:
                parsed = self._parse_json_message(item)
                if parsed:
                    messages.append(parsed)
            return {
                'type': 'batch',
                'messages': messages,
                'timestamp': datetime.now().isoformat()
            }
        else:
            return self._parse_text_message(str(data))
            
    def _parse_utrack_tweet_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析UTrack推文消息"""
        try:
            tweet = data.get('tweet', {})
            message_type = data.get('type', 'unknown')
            
            logger.info(f"🐦 [推文解析] 开始解析推文消息 - 类型: {message_type}")
            
            # 提取推文信息
            tweet_type = tweet.get('type', 'TWEET')
            author = tweet.get('author', {})
            body = tweet.get('body', {})
            
            # 提取文本内容
            tweet_text = body.get('text') or tweet.get('text') or tweet.get('content') or ''
            
            # 提取智能合约信息
            contract_info = self.extract_contract_info(tweet_text)
            if contract_info:
                logger.info(f"🔗 [CA检测] 发现智能合约信息: {len(contract_info)}项")
            
            # 提取媒体信息
            media = tweet.get('media', {})
            media_urls = []
            if media:
                if media.get('images'):
                    media_urls.extend([img.get('url', '') for img in media['images']])
                if media.get('videos'):
                    media_urls.extend([video.get('url', '') for video in media['videos']])
            
            # 提取提及用户及其简介
            mentions = []
            mentions_with_ca = []
            if body.get('mentions'):
                for mention in body['mentions']:
                    handle = mention.get('handle', '')
                    if handle:
                        mentions.append(handle)
                        
                        # 尝试从多个地方获取提及用户的简介
                        mention_description = ''
                        
                        # 1. 直接从mention对象获取
                        if mention.get('description', {}).get('text'):
                            mention_description = mention.get('description', {}).get('text', '')
                        
                        # 2. 从subtweet的author获取（如果是回复的话）
                        subtweet = tweet.get('subtweet')
                        if not mention_description and subtweet and subtweet.get('author', {}).get('handle') == handle:
                            subtweet_author = subtweet.get('author', {})
                            mention_description = subtweet_author.get('profile', {}).get('description', {}).get('text', '')
                        
                        # 3. 从其他可能的位置获取用户信息
                        if not mention_description:
                            # 可以在这里添加从其他API端点获取用户信息的逻辑
                            pass
                        
                        if mention_description:
                            # 检查简介中是否包含CA信息
                            ca_info = self.extract_contract_info(mention_description)
                            if ca_info:
                                mentions_with_ca.append({
                                    'handle': handle,
                                    'description': mention_description,
                                    'ca_info': ca_info
                                })
                                logger.info(f"🔗 [提及用户CA] @{handle} 简介中包含CA信息: {len(ca_info)}项")
            
            # 记录原始发布时间
            original_created_at = tweet.get('created_at', '')
            logger.info(f"📅 [原始时间] 推文原始发布时间: {original_created_at}")
            
            # 尝试解析时间
            parsed_time = None
            if original_created_at:
                parsed_time = self._parse_time(original_created_at)
                if parsed_time:
                    logger.info(f"📅 [解析时间] 解析后时间: {parsed_time}")
                else:
                    logger.warning(f"📅 [解析时间] 无法解析时间格式: {original_created_at}")
            
            result = {
                'type': 'utrack_tweet',
                'message_type': message_type,
                'tweet_type': tweet_type,
                'tweet_id': tweet.get('id', ''),
                'text': tweet_text,
                'contract_info': contract_info,  # 添加智能合约信息
                'author': {
                    'handle': author.get('handle', 'unknown'),
                    'name': author.get('profile', {}).get('name', 'Unknown'),
                    'avatar': author.get('profile', {}).get('avatar', ''),
                    'description': author.get('profile', {}).get('description', {}).get('text', '') if author.get('profile', {}).get('description') else ''
                },
                'created_at': original_created_at,
                'media_urls': media_urls,
                'mentions': mentions,
                'mentions_with_ca': mentions_with_ca,  # 添加包含CA的提及用户信息
                'reply_to': tweet.get('reply', {}).get('handle', '') if tweet.get('reply') else '',
                'timestamp': datetime.now().isoformat(),
                'original': data
            }
            
            logger.info(f"✅ [推文解析] 推文解析完成 - ID: {result['tweet_id']}, 作者: @{result['author']['handle']}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [推文解析] 解析UTrack推文数据失败: {e}")
            logger.error(f"❌ [推文解析] 错误详情: {type(e).__name__}: {str(e)}")
            import traceback
            logger.error(f"❌ [推文解析] 堆栈跟踪: {traceback.format_exc()}")
            return {
                'type': 'text',
                'content': str(data),
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            
    def _parse_utrack_following_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析UTrack关注消息"""
        try:
            user = data.get('user', {})
            message_type = data.get('type', 'unknown')
            
            return {
                'type': 'utrack_following',
                'message_type': message_type,
                'user': {
                    'handle': user.get('handle', 'unknown'),
                    'name': user.get('profile', {}).get('name', 'Unknown'),
                    'avatar': user.get('profile', {}).get('avatar', ''),
                    'description': user.get('profile', {}).get('description', ''),
                    'metrics': user.get('public_metrics', {})
                },
                'timestamp': datetime.now().isoformat(),
                'original': data
            }
        except Exception as e:
            logger.error(f"解析UTrack关注数据失败: {e}")
            return {
                'type': 'text',
                'content': str(data),
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            
    def _parse_utrack_profile_update_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """解析UTrack用户资料更新消息"""
        try:
            profile_data = data.get('profile', {})
            user = profile_data.get('user', {})
            before = profile_data.get('before', {})
            message_type = data.get('type', 'unknown')
            
            logger.info(f"👤 [资料更新] 开始解析用户资料更新消息 - 类型: {message_type}")
            
            # 提取用户信息
            user_info = {
                'id': user.get('id', ''),
                'handle': user.get('handle', 'unknown'),
                'name': user.get('profile', {}).get('name', 'Unknown'),
                'avatar': user.get('profile', {}).get('avatar', ''),
                'banner': user.get('profile', {}).get('banner', ''),
                'location': user.get('profile', {}).get('location', ''),
                'description': user.get('profile', {}).get('description', {}).get('text', ''),
                'url': user.get('profile', {}).get('url', ''),
                'private': user.get('private', False),
                'verified': user.get('verified', False),
                'sensitive': user.get('sensitive', False),
                'restricted': user.get('restricted', False),
                'joined_at': user.get('joined_at', ''),
                'metrics': user.get('metrics', {})
            }
            
            # 提取变更前信息
            before_info = {
                'name': before.get('profile', {}).get('name', 'Unknown'),
                'description': before.get('profile', {}).get('description', {}).get('text', ''),
                'location': before.get('profile', {}).get('location', ''),
                'url': before.get('profile', {}).get('url', ''),
                'metrics': before.get('metrics', {})
            }
            
            # 检测变更内容
            changes = []
            if user_info['name'] != before_info['name']:
                changes.append(f"昵称: {before_info['name']} → {user_info['name']}")
            if user_info['description'] != before_info['description']:
                changes.append(f"简介: {before_info['description']} → {user_info['description']}")
            if user_info['location'] != before_info['location']:
                changes.append(f"位置: {before_info['location']} → {user_info['location']}")
            if user_info['url'] != before_info['url']:
                changes.append(f"网址: {before_info['url']} → {user_info['url']}")
            
            result = {
                'type': 'utrack_profile_update',
                'message_type': message_type,
                'user': user_info,
                'before': before_info,
                'changes': changes,
                'timestamp': datetime.now().isoformat(),
                'original': data
            }
            
            logger.info(f"✅ [资料更新] 用户资料更新解析完成 - 用户: @{user_info['handle']}, 变更: {len(changes)}项")
            return result
            
        except Exception as e:
            logger.error(f"❌ [资料更新] 解析UTrack用户资料更新数据失败: {e}")
            return {
                'type': 'text',
                'content': str(data),
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }
            
    def _parse_text_message(self, text: str) -> Dict[str, Any]:
        """解析文本消息"""
        return {
            'type': 'text',
            'content': text,
            'timestamp': datetime.now().isoformat(),
            'source': 'websocket'
        }
        
    def _parse_time(self, time_str: str) -> Optional[str]:
        """解析多种时间格式并转换为本地时区"""
        if not time_str:
            return None
        
        try:
            # 尝试Unix时间戳 (秒或毫秒)
            try:
                timestamp = int(time_str)
                if timestamp > 1000000000000:  # 毫秒时间戳
                    timestamp = timestamp / 1000
                # 假设时间戳是UTC时间，转换为本地时区
                utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                local_time = utc_time.astimezone()  # 转换为本地时区
                return local_time.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
            
            # 尝试ISO格式 (2025-08-01T14:30:00Z 或 2025-08-01T14:30:00+00:00)
            if 'T' in time_str and ('Z' in time_str or '+' in time_str):
                # 处理UTC时间
                if time_str.endswith('Z'):
                    time_str = time_str.replace('Z', '+00:00')
                tweet_time = datetime.fromisoformat(time_str)
                # 转换为本地时区
                local_time = tweet_time.astimezone()
                return local_time.strftime('%Y-%m-%d %H:%M:%S')
            
            # 尝试Twitter格式 (Wed Aug 01 14:30:00 +0000 2025)
            try:
                tweet_time = datetime.strptime(time_str, '%a %b %d %H:%M:%S %z %Y')
                # 转换为本地时区
                local_time = tweet_time.astimezone()
                return local_time.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
            
            # 尝试简单日期时间格式 (2025-08-01 14:30:00)
            try:
                tweet_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                # 假设是UTC时间，转换为本地时区
                utc_time = tweet_time.replace(tzinfo=timezone.utc)
                local_time = utc_time.astimezone()
                return local_time.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
            
            # 尝试其他常见格式
            formats = [
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S',
                '%Y-%m-%dT%H:%M:%SZ',
                '%Y-%m-%dT%H:%M:%S.%fZ',
                '%Y-%m-%dT%H:%M:%S.%f',
                '%Y-%m-%d %H:%M',
                '%Y-%m-%d'
            ]
            
            for fmt in formats:
                try:
                    tweet_time = datetime.strptime(time_str, fmt)
                    # 假设是UTC时间，转换为本地时区
                    utc_time = tweet_time.replace(tzinfo=timezone.utc)
                    local_time = utc_time.astimezone()
                    return local_time.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue
            
            # 如果所有格式都失败，返回None
            return None
            
        except Exception as e:
            logger.error(f"时间解析错误: {e}, 时间字符串: {time_str}")
            return None
        
    def format_telegram_message(self, parsed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """格式化Telegram消息"""
        try:
            message_type = parsed_data.get('type', 'text')
            
            if message_type == 'utrack_tweet':
                return self._format_utrack_tweet_message(parsed_data)
            elif message_type == 'utrack_following':
                return self._format_utrack_following_message(parsed_data)
            elif message_type == 'utrack_profile_update':
                return self._format_utrack_profile_update_message(parsed_data)
            elif message_type == 'text':
                return self._format_text_message(parsed_data)
            elif message_type == 'batch':
                return self._format_batch_message(parsed_data)
            else:
                return self._format_generic_message(parsed_data)
                
        except Exception as e:
            logger.error(f"格式化Telegram消息失败: {e}")
            return None
            
    def _format_utrack_tweet_message(self, tweet_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化UTrack推文消息"""
        tweet_type = tweet_data.get('tweet_type', 'TWEET')
        author = tweet_data.get('author', {})
        text = tweet_data.get('text', '')
        mentions = tweet_data.get('mentions', [])
        mentions_with_ca = tweet_data.get('mentions_with_ca', [])  # 获取包含CA的提及用户
        reply_to = tweet_data.get('reply_to', '')
        media_urls = tweet_data.get('media_urls', [])
        created_at = tweet_data.get('created_at', '')
        contract_info = tweet_data.get('contract_info', [])  # 获取智能合约信息
        
        # 推文类型emoji映射
        type_emoji = {
            'TWEET': '📝',
            'REPLY': '💬',
            'RETWEET': '🔄',
            'QUOTE': '💭'
        }
        
        # 构建消息文本
        message_text = f"{type_emoji.get(tweet_type, '📝')} <b>推文更新</b>\n\n"
        
        # 推文类型
        message_text += f"<b>推文类型:</b> {type_emoji.get(tweet_type, '📝')} {tweet_type}\n"
        
        # 作者信息
        message_text += f"<b>用户名:</b> @{author.get('handle', 'unknown')}\n"
        if author.get('name'):
            message_text += f"<b>用户昵称:</b> {author.get('name')}\n"
        
        # 如果是回复
        if tweet_type == 'REPLY' and reply_to:
            message_text += f"<b>回复给用户:</b> @{reply_to}\n"
        
        # 推文内容
        if text:
            message_text += f"<b>推文内容:</b> {text}\n"
        
        # 智能合约信息
        if contract_info:
            message_text += f"\n<b>🔗 CA:</b>\n"
            for info in contract_info:
                message_text += f"• {info}\n"
        
        # 提及的用户
        if mentions:
            mentions_text = ', '.join([f"@{m}" for m in mentions])
            message_text += f"<b>提及用户:</b> {mentions_text}\n"
        
        # 提及用户的CA信息
        if mentions_with_ca:
            message_text += f"\n<b>🔗 提及用户CA:</b>\n"
            for mention_ca in mentions_with_ca:
                handle = mention_ca.get('handle', '')
                description = mention_ca.get('description', '')
                ca_info = mention_ca.get('ca_info', [])
                
                message_text += f"• <b>@{handle}</b>\n"
                message_text += f"  简介: {description[:100]}...\n"
                for info in ca_info:
                    message_text += f"  {info}\n"
                message_text += "\n"
        
        # 推文链接
        tweet_url = f"https://x.com/{author.get('handle', 'unknown')}/status/{tweet_data.get('tweet_id', '')}"
        message_text += f"<b>推文链接:</b> {tweet_url}\n"
        
        # 时间信息
        if created_at:
            try:
                # 尝试多种时间格式解析
                tweet_time = self._parse_time(created_at)
                if tweet_time:
                    message_text += f"<b>发布时间:</b> {tweet_time}\n"
                else:
                    message_text += f"<b>发布时间:</b> {created_at}\n"
            except Exception as e:
                logger.error(f"时间解析失败: {e}")
                message_text += f"<b>发布时间:</b> {created_at}\n"
        
        # 媒体信息
        if media_urls:
            message_text += f"<b>媒体文件:</b> {len(media_urls)} 个\n"
        
        # 截断消息长度
        if len(message_text) > config.config.MAX_MESSAGE_LENGTH:
            message_text = message_text[:config.config.MAX_MESSAGE_LENGTH - 100] + "..."
        
        # 如果有媒体，返回媒体消息
        if media_urls:
            return {
                'type': 'photo',
                'photo_url': media_urls[0],
                'caption': message_text
            }
        else:
            return {
                'type': 'text',
                'text': message_text
            }
            
    def _format_utrack_following_message(self, following_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化UTrack关注消息"""
        user = following_data.get('user', {})
        message_type = following_data.get('message_type', 'unknown')
        
        # 消息类型配置
        type_config = {
            'following.create': {'emoji': '➕', 'title': '新增关注'},
            'following.update': {'emoji': '🔄', 'title': '关注更新'},
            'following.delete': {'emoji': '➖', 'title': '取消关注'},
            'follower.create': {'emoji': '👤', 'title': '新增粉丝'},
            'follower.update': {'emoji': '🔄', 'title': '粉丝更新'},
            'follower.delete': {'emoji': '👋', 'title': '粉丝流失'}
        }
        
        config_info = type_config.get(message_type, {'emoji': '📡', 'title': '关注变动'})
        
        # 构建消息文本
        message_text = f"{config_info['emoji']} <b>{config_info['title']}</b>\n\n"
        
        if user:
            message_text += f"<b>用户名:</b> @{user.get('handle', 'unknown')}\n"
            
            if user.get('name'):
                message_text += f"<b>用户昵称:</b> {user.get('name')}\n"
            
            if user.get('description'):
                desc = user.get('description', '')[:100]
                message_text += f"<b>用户简介:</b> {desc}...\n"
            
            # 用户统计信息
            metrics = user.get('metrics', {})
            if metrics:
                message_text += f"<b>关注数:</b> {metrics.get('following_count', 0)}\n"
                message_text += f"<b>粉丝数:</b> {metrics.get('followers_count', 0)}\n"
                message_text += f"<b>推文数:</b> {metrics.get('tweet_count', 0)}\n"
            
            # 用户链接
            user_url = f"https://x.com/{user.get('handle', 'unknown')}"
            message_text += f"<b>用户链接:</b> {user_url}\n"
        
        # 时间信息
        message_text += f"<b>时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # 截断消息长度
        if len(message_text) > config.config.MAX_MESSAGE_LENGTH:
            message_text = message_text[:config.config.MAX_MESSAGE_LENGTH - 100] + "..."
        
        return {
            'type': 'text',
            'text': message_text
        }
            
    def _format_utrack_profile_update_message(self, profile_update_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化UTrack用户资料更新消息"""
        user = profile_update_data.get('user', {})
        changes = profile_update_data.get('changes', [])
        message_type = profile_update_data.get('message_type', 'unknown')
        
        # 消息类型配置
        type_config = {
            'profile.update': {'emoji': '👤', 'title': '用户资料更新'}
        }
        
        config_info = type_config.get(message_type, {'emoji': '📝', 'title': '资料更新'})
        
        # 构建消息文本
        message_text = f"{config_info['emoji']} <b>{config_info['title']}</b>\n\n"
        
        if user:
            message_text += f"<b>用户名:</b> @{user.get('handle', 'unknown')}\n"
            
            if user.get('name'):
                message_text += f"<b>用户昵称:</b> {user.get('name')}\n"
            
            if user.get('description'):
                desc = user.get('description', '')[:100]
                message_text += f"<b>用户简介:</b> {desc}...\n"
            
            if user.get('location'):
                message_text += f"<b>位置:</b> {user.get('location')}\n"
            
            # 用户统计信息
            metrics = user.get('metrics', {})
            if metrics:
                message_text += f"<b>推文数:</b> {metrics.get('tweets', 0)}\n"
                message_text += f"<b>关注数:</b> {metrics.get('friends', 0)}\n"
                message_text += f"<b>粉丝数:</b> {metrics.get('followers', 0)}\n"
                message_text += f"<b>点赞数:</b> {metrics.get('likes', 0)}\n"
            
            # 用户状态
            status_indicators = []
            if user.get('verified'):
                status_indicators.append("✅ 认证用户")
            if user.get('private'):
                status_indicators.append("🔒 私密账户")
            if user.get('sensitive'):
                status_indicators.append("⚠️ 敏感内容")
            if user.get('restricted'):
                status_indicators.append("🚫 受限账户")
            
            if status_indicators:
                message_text += f"<b>账户状态:</b> {', '.join(status_indicators)}\n"
            
            # 变更信息
            if changes:
                message_text += f"\n<b>📝 变更内容:</b>\n"
                for change in changes:
                    message_text += f"• {change}\n"
            else:
                message_text += f"\n<b>📝 变更内容:</b> 无具体变更\n"
            
            # 用户链接
            user_url = f"https://x.com/{user.get('handle', 'unknown')}"
            message_text += f"<b>用户链接:</b> {user_url}\n"
        
        # 时间信息
        message_text += f"<b>时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # 截断消息长度
        if len(message_text) > config.config.MAX_MESSAGE_LENGTH:
            message_text = message_text[:config.config.MAX_MESSAGE_LENGTH - 100] + "..."
        
        return {
            'type': 'text',
            'text': message_text
        }
            
    def _format_text_message(self, text_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化文本消息"""
        content = text_data.get('content', '')
        
        # 检查是否为Twitter相关消息
        if self.is_twitter_message(content):
            message_text = f"�� <b>Twitter消息</b>\n\n{content}"
        else:
            message_text = f"💬 <b>消息</b>\n\n{content}"
            
        # 截断消息长度
        if len(message_text) > config.config.MAX_MESSAGE_LENGTH:
            message_text = message_text[:config.config.MAX_MESSAGE_LENGTH - 100] + "..."
            
        return {
            'type': 'text',
            'text': message_text
        }
        
    def _format_batch_message(self, batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化批量消息"""
        messages = batch_data.get('messages', [])
        if not messages:
            return None
            
        # 合并所有消息
        combined_text = "📦 <b>批量消息</b>\n\n"
        for i, msg in enumerate(messages[:5], 1):  # 最多显示5条
            if msg.get('type') == 'utrack_tweet':
                user = msg.get('author', {}).get('handle', 'unknown')
                text = msg.get('text', '')[:100]
                combined_text += f"{i}. @{user}: {text}...\n"
            elif msg.get('type') == 'utrack_profile_update':
                user = msg.get('user', {}).get('handle', 'unknown')
                combined_text += f"{i}. @{user}: 用户资料更新...\n"
            else:
                content = msg.get('content', '')[:100]
                combined_text += f"{i}. {content}...\n"
                
        if len(messages) > 5:
            combined_text += f"\n... 还有 {len(messages) - 5} 条消息"
            
        return {
            'type': 'text',
            'text': combined_text
        }
        
    def _format_generic_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """格式化通用消息"""
        content = str(data)
        
        if len(content) > config.config.MAX_MESSAGE_LENGTH:
            content = content[:config.config.MAX_MESSAGE_LENGTH - 100] + "..."
            
        return {
            'type': 'text',
            'text': f"📄 <b>数据消息</b>\n\n{content}"
        } 
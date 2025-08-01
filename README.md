# Twitter推文转发到Telegram

这是一个Python版本的Twitter推文转发器，用于将WebSocket接收到的Twitter推文转发到Telegram。

## 功能特性

- 🔄 实时WebSocket连接，接收Twitter推文
- 📱 自动转发推文到Telegram
- 🖼️ 支持图片和媒体转发
- 📊 性能监控和统计
- 🔄 自动重连机制
- 📝 详细的日志记录
- ⚡ 异步处理，高性能

## 架构组件

- `main.py` - 主程序入口
- `config.py` - 配置管理
- `websocket_client.py` - WebSocket客户端
- `telegram_client.py` - Telegram客户端
- `message_processor.py` - 消息处理器

## 安装和配置

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 创建Telegram Bot

1. 在Telegram中找到 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot` 命令创建新Bot
3. 获取Bot Token

### 3. 获取Chat ID

#### 个人聊天ID：
1. 向你的Bot发送消息
2. 访问 `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. 找到 `chat.id` 字段

#### 群组Chat ID：
1. 将Bot添加到群组
2. 在群组中发送消息
3. 访问上述URL获取群组ID（通常以 `-` 开头）

### 4. 配置环境变量

复制 `env_example.txt` 为 `.env` 并填写配置：

```bash
cp env_example.txt .env
```

编辑 `.env` 文件：

```env
TELEGRAM_BOT_TOKEN=your_actual_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 使用方法

### 直接运行

```bash
python main.py
```

### 后台运行

```bash
nohup python main.py > logs/app.log 2>&1 &
```

### 使用PM2（推荐）

```bash
# 安装PM2
npm install -g pm2

# 启动服务
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 查看日志
pm2 logs telegram-forwarder

# 停止服务
pm2 stop telegram-forwarder

# 重启服务
pm2 restart telegram-forwarder
```

## 配置说明

### 主要配置项

- `WSS_URL`: WebSocket连接URL
- `TELEGRAM_BOT_TOKEN`: Telegram Bot Token
- `TELEGRAM_CHAT_ID`: 目标聊天ID
- `RECONNECT_INTERVAL`: 重连间隔（毫秒）
- `HEARTBEAT_INTERVAL`: 心跳间隔（毫秒）
- `MAX_MESSAGE_LENGTH`: 消息最大长度
- `BATCH_SIZE`: 批处理大小

### 日志配置

- 日志文件位置: `logs/telegram_forwarder.log`
- 日志级别: INFO/DEBUG/ERROR
- 日志轮转: 10MB/文件，保留7天

## 消息格式

### Twitter推文格式

```
🐦 推文

👤 用户名 (@screen_name)
⏰ 发布时间

📝 推文内容

🔗 链接:
• https://example.com
```

### 普通消息格式

```
💬 消息

消息内容
```

## 监控和统计

程序会输出以下统计信息：

- 运行时间
- 消息处理数量
- 错误数量
- 重连次数
- 连接状态

## 故障排除

### 常见问题

1. **Telegram连接失败**
   - 检查Bot Token是否正确
   - 确认Chat ID格式正确
   - 确保Bot有发送消息权限

2. **WebSocket连接失败**
   - 检查网络连接
   - 确认WebSocket URL有效
   - 查看日志中的具体错误信息

3. **消息发送失败**
   - 检查消息长度是否超限
   - 确认Telegram API限制
   - 查看错误日志

### 日志查看

```bash
# 实时查看日志
tail -f logs/telegram_forwarder.log

# 查看错误日志
grep ERROR logs/telegram_forwarder.log
```

## 性能优化

- 使用异步处理提高并发性能
- 批量处理减少API调用
- 连接池复用减少延迟
- 自动重连保证服务稳定性

## 安全注意事项

- 不要将Bot Token提交到版本控制
- 使用环境变量存储敏感信息
- 定期更新依赖包
- 监控异常访问

## 开发

### 项目结构

```
tg-retweet-utrack/
├── main.py                 # 主程序
├── config.py              # 配置管理
├── websocket_client.py    # WebSocket客户端
├── telegram_client.py     # Telegram客户端
├── message_processor.py   # 消息处理器
├── requirements.txt       # 依赖列表
├── ecosystem.config.js    # PM2配置
├── README.md             # 说明文档
├── env_example.txt       # 环境变量示例
└── logs/                 # 日志目录
```

### 添加新功能

1. 在相应模块中添加功能
2. 更新配置文件
3. 添加测试用例
4. 更新文档

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request！ 
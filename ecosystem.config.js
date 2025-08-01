module.exports = {
  apps: [
    {
      name: 'telegram-forwarder',
      script: 'main.py',
      interpreter: 'python3',
      instances: 1,
      exec_mode: 'fork',
      
      // 自动重启配置
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
      
      // 日志配置
      log_file: './logs/combined.log',
      out_file: './logs/out.log',
      error_file: './logs/error.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      merge_logs: true,
      
      // 环境变量
      env: {
        NODE_ENV: 'production',
        PYTHONPATH: '.',
        LOG_LEVEL: 'INFO'
      },
      
      // 开发环境配置
      env_dev: {
        NODE_ENV: 'development',
        LOG_LEVEL: 'DEBUG'
      },
      
      // 监控配置
      watch: false,
      ignore_watch: ['node_modules', 'logs', '*.log', '__pycache__', '*.pyc'],
      
      // 内存和CPU限制
      max_memory_restart: '500M',
      
      // 其他配置
      kill_timeout: 5000,
      listen_timeout: 3000,
      
      // 健康检查
      health_check_grace_period: 3000,
      
      // 环境变量文件
      env_file: '.env',
      
      // 启动参数
      args: '',
      
      // 工作目录
      cwd: './',
      
      // 错误处理
      error_file: './logs/error.log',
      out_file: './logs/out.log',
      
      // 日志格式
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      
      // 合并日志
      merge_logs: true,
      
      // 集群配置（如果需要）
      // instances: 'max',
      // exec_mode: 'cluster'
    }
  ]
}; 
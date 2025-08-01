#!/bin/bash

# Twitter推文转发到Telegram启动脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查Python版本
check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python3 未安装，请先安装Python3"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_info "Python版本: $PYTHON_VERSION"
}

# 检查依赖
check_dependencies() {
    print_info "检查Python依赖..."
    
    if [ ! -f "requirements.txt" ]; then
        print_error "requirements.txt 文件不存在"
        exit 1
    fi
    
    # 检查是否安装了依赖
    if ! python3 -c "import websockets, telegram, loguru, pydantic" 2>/dev/null; then
        print_warning "依赖未安装，正在安装..."
        pip3 install -r requirements.txt
        print_success "依赖安装完成"
    else
        print_success "依赖检查通过"
    fi
}

# 检查配置文件
check_config() {
    print_info "检查配置文件..."
    
    if [ ! -f ".env" ]; then
        print_warning ".env 文件不存在，正在创建..."
        if [ -f "env_example.txt" ]; then
            cp env_example.txt .env
            print_warning "请编辑 .env 文件并配置Telegram Bot Token和Chat ID"
            print_info "运行以下命令编辑配置:"
            echo "  nano .env"
            exit 1
        else
            print_error "env_example.txt 文件不存在"
            exit 1
        fi
    fi
    
    # 检查必要的环境变量
    if ! grep -q "TELEGRAM_BOT_TOKEN=" .env || ! grep -q "TELEGRAM_CHAT_ID=" .env; then
        print_error "请在 .env 文件中配置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID"
        exit 1
    fi
    
    print_success "配置文件检查通过"
}

# 创建日志目录
create_logs_dir() {
    if [ ! -d "logs" ]; then
        print_info "创建日志目录..."
        mkdir -p logs
        print_success "日志目录创建完成"
    fi
}

# 启动服务
start_service() {
    print_info "启动Twitter推文转发服务..."
    
    # 检查是否已经在运行
    if pgrep -f "python3 main.py" > /dev/null; then
        print_warning "服务已经在运行中"
        return
    fi
    
    # 启动服务
    nohup python3 main.py > logs/app.log 2>&1 &
    PID=$!
    
    # 等待服务启动
    sleep 2
    
    if kill -0 $PID 2>/dev/null; then
        print_success "服务启动成功 (PID: $PID)"
        echo $PID > .pid
    else
        print_error "服务启动失败，请检查日志: logs/app.log"
        exit 1
    fi
}

# 停止服务
stop_service() {
    print_info "停止服务..."
    
    if [ -f ".pid" ]; then
        PID=$(cat .pid)
        if kill -0 $PID 2>/dev/null; then
            kill $PID
            rm .pid
            print_success "服务已停止"
        else
            print_warning "服务未在运行"
            rm -f .pid
        fi
    else
        # 尝试通过进程名停止
        if pgrep -f "python3 main.py" > /dev/null; then
            pkill -f "python3 main.py"
            print_success "服务已停止"
        else
            print_warning "服务未在运行"
        fi
    fi
}

# 重启服务
restart_service() {
    print_info "重启服务..."
    stop_service
    sleep 2
    start_service
}

# 查看状态
show_status() {
    print_info "服务状态:"
    
    if [ -f ".pid" ]; then
        PID=$(cat .pid)
        if kill -0 $PID 2>/dev/null; then
            print_success "服务正在运行 (PID: $PID)"
        else
            print_error "服务未运行 (PID文件存在但进程不存在)"
            rm -f .pid
        fi
    else
        if pgrep -f "python3 main.py" > /dev/null; then
            PID=$(pgrep -f "python3 main.py")
            print_success "服务正在运行 (PID: $PID)"
        else
            print_warning "服务未运行"
        fi
    fi
}

# 查看日志
show_logs() {
    if [ -f "logs/app.log" ]; then
        print_info "显示最新日志 (按 Ctrl+C 退出):"
        tail -f logs/app.log
    else
        print_warning "日志文件不存在"
    fi
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            check_python
            check_dependencies
            check_config
            create_logs_dir
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            check_python
            check_dependencies
            check_config
            create_logs_dir
            restart_service
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        install)
            check_python
            check_dependencies
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status|logs|install}"
            echo ""
            echo "命令:"
            echo "  start   - 启动服务"
            echo "  stop    - 停止服务"
            echo "  restart - 重启服务"
            echo "  status  - 查看状态"
            echo "  logs    - 查看日志"
            echo "  install - 安装依赖"
            exit 1
            ;;
    esac
}

# 运行主函数
main "$@" 
#!/bin/bash
set -euo pipefail

# AIOS-NP 每日新闻生成定时脚本
# 每天0点自动运行，生成当日新闻报

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export WORK_DIR="$SCRIPT_DIR"
export PYTHONPATH="$WORK_DIR:${PYTHONPATH:-}"
export AIOS_NP_DATA_DIR="${AIOS_NP_DATA_DIR:-$WORK_DIR}"
export AIOS_NP_LOG_DIR="${AIOS_NP_LOG_DIR:-$WORK_DIR/logs}"
export PYTHON_BIN="${PYTHON_BIN:-$WORK_DIR/.venv/bin/python}"

if [ -f "$WORK_DIR/.env.local" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$WORK_DIR/.env.local"
    set +a
fi

# 日志文件路径
LOG_DIR="${AIOS_NP_LOG_DIR}"
mkdir -p "$LOG_DIR"

# 获取当前日期
DATE=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/daily_news_$DATE.log"

# 检查AIOS内核是否运行
check_aios_kernel() {
    if ! curl -fsS http://localhost:8001/status > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: AIOS内核未运行，正在启动..." >> "$LOG_FILE"
        cd "$WORK_DIR"
        nohup "$PYTHON_BIN" -m runtime.launch > "$LOG_DIR/aios_kernel_$DATE.log" 2>&1 &
        sleep 10
        
        # 再次检查
        if ! curl -fsS http://localhost:8001/status > /dev/null 2>&1; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: AIOS内核启动失败" >> "$LOG_FILE"
            exit 1
        fi
    fi
}

# 运行新闻生成流水线
run_news_pipeline() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - 开始生成每日新闻报..." >> "$LOG_FILE"
    
    cd "$WORK_DIR"
    
    # 检查API密钥
    if [ -z "$ZH_API_KEY" ] || [ -z "$TAVILY_API_KEY" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: 缺少API密钥环境变量" >> "$LOG_FILE"
        echo "请设置 ZH_API_KEY 和 TAVILY_API_KEY 环境变量" >> "$LOG_FILE"
        exit 1
    fi
    
    # 运行并行流水线
    "$PYTHON_BIN" parallel_pipeline.py \
        --zh_api_key "$ZH_API_KEY" \
        --tavily_api_key "$TAVILY_API_KEY" \
        >> "$LOG_FILE" 2>&1
    
    if [ $? -eq 0 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 新闻报生成成功" >> "$LOG_FILE"
        
        # 移动生成的新闻报到output目录
        if [ -f "output/新闻报_$(date +%Y%m%d)_*.txt" ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') - 新闻报已保存到output目录" >> "$LOG_FILE"
        fi
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') - 错误: 新闻报生成失败" >> "$LOG_FILE"
        exit 1
    fi
}

# 清理旧日志文件（保留7天）
cleanup_old_logs() {
    find "$LOG_DIR" -name "daily_news_*.log" -mtime +7 -delete
    find "$LOG_DIR" -name "aios_kernel_*.log" -mtime +7 -delete
}

# 主函数
main() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ===== AIOS-NP 每日新闻生成开始 =====" >> "$LOG_FILE"
    
    # 检查AIOS内核
    check_aios_kernel
    
    # 运行新闻生成
    run_news_pipeline
    
    # 清理旧日志
    cleanup_old_logs
    
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ===== AIOS-NP 每日新闻生成完成 =====" >> "$LOG_FILE"
}

# 执行主函数
main "$@"

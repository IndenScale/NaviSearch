#!/bin/bash

# NaviSearch 项目启动脚本
# 同时启动 FastAPI 后端（带虚拟环境）和 React 前端 (Vite)

# 定义颜色代码
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # 重置颜色

# 获取脚本所在目录（项目根目录）
BASE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# 检查后端目录
BACKEND_DIR="${BASE_DIR}/backend"
if [ ! -f "${BACKEND_DIR}/main.py" ]; then
  echo -e "${RED}错误: 未找到后端目录 (${BACKEND_DIR})${NC}"
  exit 1
fi

# 检查前端目录
FRONTEND_DIR="${BASE_DIR}/frontend"
if [ ! -f "${FRONTEND_DIR}/package.json" ]; then
  echo -e "${RED}错误: 未找到前端目录 (${FRONTEND_DIR})${NC}"
  exit 1
fi

# 清理函数，用于终止后台进程
cleanup() {
  echo -e "\n${YELLOW}正在停止所有进程...${NC}"
  kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
  # 停用虚拟环境（如果在后端目录激活）
  if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
  fi
  exit 0
}

# 捕获退出信号
trap cleanup SIGINT SIGTERM

# 启动后端服务器（带虚拟环境检查）
start_backend() {
  echo -e "${GREEN}启动 FastAPI 后端服务器...${NC}"
  cd "${BACKEND_DIR}"
  
  # 检查虚拟环境
  VENV_PATH=""
  if [ -d ".venv" ]; then
    VENV_PATH=".venv"
    echo -e "${CYAN}检测到虚拟环境: ${VENV_PATH}${NC}"
  elif [ -d "venv" ]; then
    VENV_PATH="venv"
    echo -e "${CYAN}检测到虚拟环境: ${VENV_PATH}${NC}"
  fi

  # 激活虚拟环境
  if [ -n "$VENV_PATH" ]; then
    source "${VENV_PATH}/bin/activate"
    echo -e "${CYAN}已激活虚拟环境${NC}"
    python -m pip list | grep uvicorn
  else
    echo -e "${YELLOW}警告: 未找到虚拟环境，使用系统Python${NC}"
  fi

  # 启动后端
  python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000 &
  BACKEND_PID=$!
  echo -e "后端 PID: ${YELLOW}${BACKEND_PID}${NC} (http://localhost:8000)"
}

# 启动前端服务器
start_frontend() {
  echo -e "${GREEN}启动 Vite 前端服务器...${NC}"
  cd "${FRONTEND_DIR}"
  
  # 检查node_modules是否存在
  if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}警告: node_modules 不存在，正在安装依赖...${NC}"
    npm install
  fi
  
  npm run dev &
  FRONTEND_PID=$!
  echo -e "前端 PID: ${YELLOW}${FRONTEND_PID}${NC} (http://localhost:3000)"
}

# 检查端口占用
check_port() {
  local port=$1
  local service=$2
  if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}错误: 端口 $port 已被占用 ($service)${NC}"
    exit 1
  fi
}

# 主函数
main() {
  echo -e "\n${GREEN}>>> 启动 NaviSearch 项目 <<<${NC}"
  
  # 检查端口占用
  check_port 8000 "后端"
  check_port 3000 "前端"
  
  start_backend
  start_frontend
  
  echo -e "\n${YELLOW}两个服务器已启动。按 Ctrl+C 停止...${NC}"
  echo -e "${YELLOW}-------------------------------------------${NC}"
  echo -e "${GREEN}后端 API:    http://localhost:8000${NC}"
  echo -e "${GREEN}前端开发服务器: http://localhost:3000${NC}"
  echo -e "${YELLOW}-------------------------------------------${NC}"
  
  # 保持脚本运行，直到收到中断信号
  wait
}

# 执行主函数
main
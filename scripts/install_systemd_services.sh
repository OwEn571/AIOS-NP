#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="$PROJECT_ROOT/deploy/systemd"

sudo cp "$SYSTEMD_DIR/aios-kernel.service" /etc/systemd/system/aios-kernel.service
sudo cp "$SYSTEMD_DIR/aios-news-ecosystem.service" /etc/systemd/system/aios-news-ecosystem.service
sudo cp "$SYSTEMD_DIR/aios-news-mcp.service" /etc/systemd/system/aios-news-mcp.service

sudo systemctl daemon-reload
sudo systemctl enable aios-kernel.service
sudo systemctl enable aios-news-ecosystem.service
sudo systemctl enable aios-news-mcp.service

echo "已安装并启用 systemd 服务："
echo "  - aios-kernel.service"
echo "  - aios-news-ecosystem.service"
echo "  - aios-news-mcp.service"

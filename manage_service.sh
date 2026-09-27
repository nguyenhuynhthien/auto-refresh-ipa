#!/bin/bash
set -e

PLIST_NAME="com.user.autorefresh.ipa.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

case "$1" in
    install)
        echo "==> Đang cài đặt dịch vụ chạy ngầm và Menu Bar..."
        mkdir -p "$HOME/Library/LaunchAgents"
        cp "$SCRIPT_DIR/com.user.autorefresh.ipa.plist" "$HOME/Library/LaunchAgents/"
        cp "$SCRIPT_DIR/com.user.autorefresh.menubar.plist" "$HOME/Library/LaunchAgents/"
        
        launchctl unload "$HOME/Library/LaunchAgents/com.user.autorefresh.ipa.plist" 2>/dev/null || true
        launchctl load "$HOME/Library/LaunchAgents/com.user.autorefresh.ipa.plist"
        
        launchctl unload "$HOME/Library/LaunchAgents/com.user.autorefresh.menubar.plist" 2>/dev/null || true
        launchctl load "$HOME/Library/LaunchAgents/com.user.autorefresh.menubar.plist"
        
        echo "==> Đã cài đặt thành công! Menu Bar icon và Daemon tự động chạy cùng máy."
        echo "Log xuất tại: $SCRIPT_DIR/logs/"
        ;;
    uninstall)
        echo "==> Đang gỡ bỏ LaunchAgents..."
        launchctl unload "$HOME/Library/LaunchAgents/com.user.autorefresh.ipa.plist" 2>/dev/null || true
        launchctl unload "$HOME/Library/LaunchAgents/com.user.autorefresh.menubar.plist" 2>/dev/null || true
        rm -f "$HOME/Library/LaunchAgents/com.user.autorefresh.ipa.plist"
        rm -f "$HOME/Library/LaunchAgents/com.user.autorefresh.menubar.plist"
        echo "==> Đã gỡ bỏ toàn bộ dịch vụ chạy ngầm và Menu Bar."
        ;;
    status)
        echo "==> Trạng thái LaunchAgents:"
        launchctl list | grep "com.user.autorefresh" || echo "Chưa active."
        ;;
    run-now)
        echo "==> Kích hoạt chạy thủ công ngay lập tức (Force refresh):"
        python3 "$SCRIPT_DIR/auto_refresh.py" --force
        ;;
    uninstall-app)
        echo "==> Gỡ cài đặt ứng dụng khỏi iPhone..."
        python3 -c "
import auto_refresh
cfg = auto_refresh.load_config()
dev = auto_refresh.get_connected_device(cfg)
if not dev:
    print('Chưa kết nối iPhone!')
    exit(1)
bundle_id = cfg.get('bundle_id')
if dev['tool'] == 'devicectl':
    auto_refresh.run_command(['xcrun', 'devicectl', 'device', 'uninstall', 'app', '--device', dev['udid'], bundle_id])
elif dev['tool'] == 'ideviceinstaller':
    auto_refresh.run_command(['ideviceinstaller', '-u', dev['udid'], '-U', bundle_id])
elif dev['tool'] == 'pymobiledevice3':
    auto_refresh.run_command(['pymobiledevice3', 'apps', 'uninstall', bundle_id])
print('Đã gỡ cài đặt app', bundle_id)
"
        ;;
    gui)
        echo "==> Mở giao diện ứng dụng..."
        python3 "$SCRIPT_DIR/gui_app.py"
        ;;
    menubar)
        echo "==> Chạy ứng dụng trên thanh Menu Bar macOS..."
        python3 "$SCRIPT_DIR/menubar_app.py"
        ;;
    *)
        echo "Cách sử dụng: $0 {install|uninstall|status|run-now|uninstall-app|gui|menubar}"
        exit 1
        ;;
esac

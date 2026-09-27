#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IPA_PLIST="$HOME/Library/LaunchAgents/com.user.autorefresh.ipa.plist"
MENUBAR_PLIST="$HOME/Library/LaunchAgents/com.user.autorefresh.menubar.plist"

echo "============================================================"
echo "      BẮT ĐẦU QUY TRÌNH GỠ BỎ HOÀN TOÀN AUTO-REFRESH-IPA    "
echo "============================================================"

# 1. Tắt tiến trình Menu Bar đang chạy và gỡ bỏ LaunchAgents
echo "1. Đang dừng và gỡ bỏ Menu Bar App & Background Daemon..."

# Hủy đăng ký LaunchAgents khỏi launchd
launchctl unload "$IPA_PLIST" 2>/dev/null || true
launchctl unload "$MENUBAR_PLIST" 2>/dev/null || true

# Xóa các file .plist khởi động cùng máy
rm -f "$IPA_PLIST"
rm -f "$MENUBAR_PLIST"
echo "-> Đã xóa các file LaunchAgents trong ~/Library/LaunchAgents/."

# Tắt trực tiếp tiến trình menubar_app.py nếu đang chạy
pkill -f "menubar_app.py" 2>/dev/null || true
echo "-> Đã đóng Menu Bar App trên màn hình."

# 2. Xóa các file build tạm, logs và state
echo "2. Đang dọn dẹp thư mục build, logs và trạng thái..."
rm -rf "$SCRIPT_DIR/build"
rm -rf "$SCRIPT_DIR/logs"
rm -f "$SCRIPT_DIR/last_refresh_state.json"
echo "-> Đã xóa sạch logs, cache và trạng thái."

# 3. Hỏi người dùng có muốn gỡ app trên iPhone trước khi xóa code không
read -p "3. Bạn có muốn gỡ cài đặt app trên iPhone luôn không? (y/N): " choice
if [[ "$choice" =~ ^[Yy]$ ]]; then
    echo "-> Đang gửi lệnh gỡ app trên iPhone..."
    python3 -c "
import auto_refresh
try:
    cfg = auto_refresh.load_config()
    dev = auto_refresh.get_connected_device(cfg)
    if dev:
        b_id = cfg.get('bundle_id')
        auto_refresh.run_command(['xcrun', 'devicectl', 'device', 'uninstall', 'app', '--device', dev['udid'], b_id])
        print('-> Đã gỡ thành công app', b_id, 'khỏi iPhone!')
    else:
        print('-> Không tìm thấy iPhone đang kết nối.')
except Exception as e:
    print('-> Bỏ qua gỡ iPhone:', e)
" || true
fi

echo ""
echo "============================================================"
echo "🎉 ĐÃ GỠ BỎ SẠCH SẼ 100% HỆ THỐNG KHỎI MACOS!"
echo "-> Menu Bar đã được đóng và gỡ bỏ hoàn toàn."
echo "-> LaunchAgents đã tắt hoàn toàn (không tự chạy khi khởi động)."
echo "-> Để xóa toàn bộ thư mục code này, bạn chỉ cần chạy lệnh:"
echo "   rm -rf \"$SCRIPT_DIR\""
echo "============================================================"

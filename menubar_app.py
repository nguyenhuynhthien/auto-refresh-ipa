#!/usr/bin/env python3
"""
Menu Bar App cho macOS (Auto-Refresh-IPA)
Hiển thị icon trạng thái tinh gọn trên thanh Menu Bar macOS:
- Toàn bộ text menu đều có callback hoặc được kích hoạt trạng thái enabled để chữ luôn ĐẬM, RÕ NÉT, không bị mờ/disabled.
- Cho phép click trực tiếp vào ứng dụng để Refresh ngay.
"""

import sys
import subprocess
import threading
from pathlib import Path
import rumps

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import auto_refresh


try:
    import AppKit
    # Chuyển ứng dụng sang Accessory mode (chỉ hiện trên Menu Bar, ẩn hoàn toàn khỏi thanh Dock)
    _ns_app = AppKit.NSApplication.sharedApplication()
    _ns_app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
except Exception:
    pass

def dummy_callback(_):
    """Callback rỗng để macOS không tự động làm mờ (disable/gray out) menu item"""
    pass


ICON_PATH = str(BASE_DIR / "assets" / "menubar_icon.png")


class AutoRefreshMenuBarApp(rumps.App):
    def __init__(self):
        super().__init__("AutoRefresh", icon=ICON_PATH, template=True, quit_button=None)
        try:
            import AppKit
            AppKit.NSApplication.sharedApplication().setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        except Exception:
            pass
        self.title = None
        self.rebuild_menu()

    def rebuild_menu(self):
        """Xây dựng lại toàn bộ cấu trúc Menu sắc nét, rõ ràng 100%"""
        try:
            devices = auto_refresh.list_available_devices()
            online_devs = [d for d in devices if d.get("is_ready")]
            records = auto_refresh.load_all_records()

            # Giữ icon template trắng đen phẳng chuẩn macOS, không chèn emoji
            self.title = None

            menu_items = []

            # --- PHẦN 1: THIẾT BỊ ---
            header_dev = rumps.MenuItem("📱 THIẾT BỊ IPHONE", callback=dummy_callback)
            menu_items.append(header_dev)

            if not devices:
                item_nodev = rumps.MenuItem("   (Chưa nhận diện thiết bị nào)", callback=dummy_callback)
                menu_items.append(item_nodev)
            else:
                for d in devices:
                    status_icon = "🟢 Online" if d["is_ready"] else "⚪ Offline"
                    dev_text = f"   {d['name']} ({d['model']}) • {status_icon}"
                    dev_item = rumps.MenuItem(dev_text, callback=dummy_callback)
                    menu_items.append(dev_item)

            menu_items.append(rumps.separator)

            # --- PHẦN 2: ỨNG DỤNG ĐANG QUẢN LÝ ---
            header_app = rumps.MenuItem("📦 ỨNG DỤNG ĐANG QUẢN LÝ", callback=dummy_callback)
            menu_items.append(header_app)

            if not records:
                item_noapp = rumps.MenuItem("   (Chưa có ứng dụng nào)", callback=dummy_callback)
                menu_items.append(item_noapp)
            else:
                for k, rec in records.items():
                    app_name = rec.get("app_name", "App")
                    dev_name = rec.get("device_name", "iPhone")
                    bundle_id = rec.get("bundle_id", "")
                    _, rem = auto_refresh.calculate_remaining(rec.get("last_refresh_time", ""))
                    if rem > 0:
                        rem_text = f"🟢 Còn {rem:.1f} ngày"
                    elif rem == -1.0:
                        rem_text = "Chưa rõ"
                    else:
                        rem_text = f"🔴 Hết hạn ({abs(rem):.1f}d)"

                    app_title = f"   {app_name} [{dev_name}] • {rem_text}"
                    app_menu_item = rumps.MenuItem(app_title, callback=dummy_callback)

                    # Submenu khi click vào app
                    action_refresh = rumps.MenuItem(
                        f"🚀 Ký & Refresh '{app_name}' ngay",
                        callback=lambda sender, r=rec: self.refresh_specific_app(r)
                    )
                    app_info = rumps.MenuItem(f"ℹ️ Bundle ID: {bundle_id}", callback=dummy_callback)
                    last_seen = rumps.MenuItem(f"🕒 Lần ký: {rec.get('last_refresh_local', 'N/A')}", callback=dummy_callback)

                    app_menu_item.add(action_refresh)
                    app_menu_item.add(rumps.separator)
                    app_menu_item.add(app_info)
                    app_menu_item.add(last_seen)

                    menu_items.append(app_menu_item)

            menu_items.append(rumps.separator)

            # --- PHẦN 3: THAO TÁC CHUNG ---
            menu_items.append(rumps.MenuItem("🚀 Ký & Refresh tất cả", callback=self.on_refresh_all))
            menu_items.append(rumps.MenuItem("🖥️ Mở Dashboard GUI...", callback=self.on_open_gui))
            menu_items.append(rumps.MenuItem("🔄 Quét lại trạng thái", callback=self.on_manual_update))
            menu_items.append(rumps.separator)
            menu_items.append(rumps.MenuItem("Thoát", callback=rumps.quit_application))

            self.menu.clear()
            self.menu = menu_items

        except Exception as e:
            pass

    @rumps.timer(30)
    def periodic_update(self, _):
        self.rebuild_menu()

    def on_manual_update(self, _):
        self.rebuild_menu()

    def refresh_specific_app(self, record):
        """Ký và nạp lại riêng cho 1 ứng dụng được click"""
        def worker():
            app_name = record.get("app_name", "App")
            bundle_id = record.get("bundle_id", "")
            target_udid = record.get("device_udid", "")
            ipa_source = record.get("ipa_source", "")

            try:
                rumps.notification("Auto-Refresh IPA", f"Đang refresh {app_name}...", "Vui lòng chờ trong giây lát")
                config = auto_refresh.load_config()

                available_devices = {d["udid"]: d for d in auto_refresh.list_available_devices()}
                target_dev = None
                if target_udid and target_udid in available_devices:
                    target_dev = available_devices[target_udid]
                else:
                    online = [d for d in available_devices.values() if d["is_ready"]]
                    if online:
                        target_dev = online[0]

                if not target_dev or not target_dev.get("is_ready"):
                    rumps.notification("Auto-Refresh IPA", f"Không thể kết nối {record.get('device_name', 'iPhone')}", "Vui lòng cắm cáp USB và mở khóa iPhone!")
                    return

                identity = auto_refresh.find_signing_identity(config)
                success = auto_refresh.refresh_single_app(ipa_source, bundle_id, target_dev, identity, app_name)
                if success:
                    rumps.notification("Auto-Refresh IPA", "Thành công!", f"Đã refresh thành công '{app_name}' (7 ngày)")
                    self.rebuild_menu()
            except Exception as e:
                rumps.notification("Auto-Refresh IPA Lỗi", f"Lỗi refresh {app_name}", str(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_refresh_all(self, _):
        def worker():
            try:
                rumps.notification("Auto-Refresh IPA", "Đang ký & refresh tất cả ứng dụng...", "Vui lòng chờ...")
                subprocess.run([sys.executable, str(BASE_DIR / "auto_refresh.py"), "--force"], check=True)
                rumps.notification("Auto-Refresh IPA", "Hoàn tất!", "Đã refresh thành công các ứng dụng đủ điều kiện.")
                self.rebuild_menu()
            except Exception as e:
                rumps.notification("Auto-Refresh IPA Lỗi", "Thất bại", str(e))

        threading.Thread(target=worker, daemon=True).start()

    def on_open_gui(self, _):
        subprocess.Popen([sys.executable, str(BASE_DIR / "gui_app.py")])


def main():
    app = AutoRefreshMenuBarApp()
    app.run()


if __name__ == "__main__":
    main()

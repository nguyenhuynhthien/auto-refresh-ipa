#!/usr/bin/env python3
"""
GUI Dashboard cho Auto-Refresh-IPA.
Giao diện Dark Theme hiện đại, tương phản cực cao, khắc phục hoàn toàn lỗi màu của Tkinter trên macOS.
Quản lý danh sách ứng dụng đã cài đặt trên các thiết bị, theo dõi số ngày còn hạn và refresh.
"""

import os
import sys
import json
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import auto_refresh


class CustomButton(tk.Canvas):
    """Nút bấm tùy chỉnh bằng Canvas với độ tương phản cao và render màu chuẩn xác 100% trên macOS"""
    def __init__(self, parent, text, command=None, bg_color="#0284c7", fg_color="#ffffff", hover_color="#0369a1", font=("Helvetica", 11, "bold"), height=38, width=None):
        super().__init__(parent, bg=parent["bg"], highlightthickness=0, bd=0, height=height)
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_color = hover_color
        self.current_bg = bg_color
        self.font = font
        self.text = text
        self.is_enabled = True

        if width:
            self.config(width=width)

        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return

        # Vẽ nền bo góc nhẹ
        r = 6
        self.create_polygon(
            r, 0, w - r, 0, w, 0, w, r, w, h - r, w, h, w - r, h, r, h, 0, h, 0, h - r, 0, r, 0, 0,
            fill=self.current_bg, outline="#38bdf8" if self.current_bg == self.bg_color else "#ffffff", width=1, smooth=True
        )

        # Vẽ text ở giữa
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg_color, font=self.font)

    def _on_enter(self, event):
        if self.is_enabled:
            self.current_bg = self.hover_color
            self.config(cursor="hand2")
            self._draw()

    def _on_leave(self, event):
        if self.is_enabled:
            self.current_bg = self.bg_color
            self.config(cursor="")
            self._draw()

    def _on_click(self, event):
        if self.is_enabled and self.command:
            self.command()

    def set_text(self, new_text, bg_color=None, fg_color=None):
        self.text = new_text
        if bg_color:
            self.bg_color = bg_color
            self.current_bg = bg_color
        if fg_color:
            self.fg_color = fg_color
        self._draw()

    def set_enabled(self, enabled):
        self.is_enabled = enabled
        if not enabled:
            self.current_bg = "#334155"
            self.fg_color = "#94a3b8"
        else:
            self.current_bg = self.bg_color
            self.fg_color = "#ffffff"
        self._draw()


class ModernAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("⚡ iOS IPA Auto Refresh & Device Manager")
        self.root.geometry("980x790")
        self.root.minsize(900, 680)
        self.root.configure(bg="#0f172a")

        # Đưa cửa sổ lên trên cùng (Foreground / Focus) trên macOS
        self.bring_to_front()

        self.setup_styles()
        self.build_ui()
        self.load_config_values()
        self.reload_devices_list()
        self.reload_apps_table()

    def bring_to_front(self):
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(200, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
            # Kích hoạt AppleScript đưa ứng dụng lên foreground
            subprocess.run(["osascript", "-e", 'tell application "System Events" to set frontmost of first process whose unix id is %d to true' % os.getpid()], check=False)
        except Exception:
            pass

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        # Cấu hình Treeview (Bảng quản lý app & hạn dùng)
        style.configure(
            "Treeview",
            background="#1e293b",
            foreground="#f8fafc",
            fieldbackground="#1e293b",
            rowheight=32,
            font=("Helvetica", 11)
        )
        style.configure(
            "Treeview.Heading",
            background="#334155",
            foreground="#38bdf8",
            font=("Helvetica", 11, "bold"),
            relief="flat"
        )
        style.map("Treeview", background=[("selected", "#0284c7")], foreground=[("selected", "#ffffff")])

        # Cấu hình Combobox
        style.configure(
            "TCombobox",
            fieldbackground="#1e293b",
            background="#334155",
            foreground="#f8fafc",
            darkcolor="#0f172a",
            lightcolor="#334155",
            arrowcolor="#38bdf8"
        )
        style.map("TCombobox", fieldbackground=[("readonly", "#1e293b")], selectbackground=[("readonly", "#0284c7")])

    def build_ui(self):
        # 1. Header Banner
        header = tk.Frame(self.root, bg="#1e293b", height=70, padx=20, pady=12, highlightthickness=1, highlightbackground="#334155")
        header.pack(fill="x", side="top")

        title_lbl = tk.Label(header, text="⚡ iOS IPA Auto Refresh & Device Manager", font=("Helvetica", 16, "bold"), bg="#1e293b", fg="#f8fafc")
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(header, text="Duy trì chứng chỉ 7 ngày Free - Quản lý ứng dụng & theo dõi số ngày còn hạn", font=("Helvetica", 11), bg="#1e293b", fg="#94a3b8")
        sub_lbl.pack(anchor="w")

        # Container chính
        main_box = tk.Frame(self.root, bg="#0f172a", padx=16, pady=10)
        main_box.pack(fill="both", expand=True)

        # 2. Card: Cấu hình IPA & Thiết bị
        cfg_card = tk.LabelFrame(main_box, text="  Cấu hình Ký & Thiết bị mục tiêu  ", font=("Helvetica", 12, "bold"), bg="#1e293b", fg="#38bdf8", padx=14, pady=10, relief="solid", bd=1)
        cfg_card.pack(fill="x", pady=6)

        # Hàng 1: Chọn thiết bị
        row_dev = tk.Frame(cfg_card, bg="#1e293b")
        row_dev.pack(fill="x", pady=4)
        tk.Label(row_dev, text="Thiết bị iPhone:", width=14, anchor="w", bg="#1e293b", fg="#f8fafc", font=("Helvetica", 11, "bold")).pack(side="left")
        
        self.device_select_var = tk.StringVar()
        self.device_combo = ttk.Combobox(row_dev, textvariable=self.device_select_var, state="readonly", font=("Helvetica", 11))
        self.device_combo.pack(side="left", fill="x", expand=True, padx=6)
        self.device_combo.bind("<<ComboboxSelected>>", self.on_device_selected)

        self.reload_dev_btn = CustomButton(
            row_dev, text="🔄 Quét thiết bị", bg_color="#334155", fg_color="#38bdf8", hover_color="#475569",
            font=("Helvetica", 10, "bold"), height=30, width=120, command=self.reload_devices_list
        )
        self.reload_dev_btn.pack(side="right")

        # Hàng 2: File IPA
        row_ipa = tk.Frame(cfg_card, bg="#1e293b")
        row_ipa.pack(fill="x", pady=4)
        tk.Label(row_ipa, text="File IPA nguồn:", width=14, anchor="w", bg="#1e293b", fg="#f8fafc", font=("Helvetica", 11, "bold")).pack(side="left")
        
        self.ipa_path_var = tk.StringVar()
        self.ipa_entry = tk.Entry(row_ipa, textvariable=self.ipa_path_var, font=("Helvetica", 11), bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", relief="solid", bd=1)
        self.ipa_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=3)

        self.browse_btn = CustomButton(
            row_ipa, text="📁 Chọn IPA...", bg_color="#334155", fg_color="#f8fafc", hover_color="#475569",
            font=("Helvetica", 10, "bold"), height=30, width=120, command=self.browse_ipa
        )
        self.browse_btn.pack(side="right")

        # Hàng 3: Bundle ID & Chu kỳ refresh
        row_meta = tk.Frame(cfg_card, bg="#1e293b")
        row_meta.pack(fill="x", pady=4)
        tk.Label(row_meta, text="Bundle ID:", width=14, anchor="w", bg="#1e293b", fg="#f8fafc", font=("Helvetica", 11, "bold")).pack(side="left")
        
        self.bundle_id_var = tk.StringVar()
        self.bundle_entry = tk.Entry(row_meta, textvariable=self.bundle_id_var, font=("Helvetica", 11), bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", relief="solid", bd=1)
        self.bundle_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=3)

        tk.Label(row_meta, text="Chu kỳ refresh:", bg="#1e293b", fg="#f8fafc", font=("Helvetica", 11, "bold")).pack(side="left", padx=(10, 4))
        self.interval_var = tk.StringVar(value="4")
        self.interval_entry = tk.Entry(row_meta, textvariable=self.interval_var, width=4, font=("Helvetica", 11, "bold"), bg="#0f172a", fg="#38bdf8", insertbackground="#ffffff", relief="solid", bd=1, justify="center")
        self.interval_entry.pack(side="left", ipady=3)
        tk.Label(row_meta, text="ngày", bg="#1e293b", fg="#94a3b8", font=("Helvetica", 11)).pack(side="left", padx=3)

        # 3. Card: Bảng theo dõi các App đã cài đặt & Số ngày còn hạn
        table_card = tk.LabelFrame(main_box, text="  Quản lý Ứng dụng & Thời hạn Chứng chỉ (7 ngày Free)  ", font=("Helvetica", 12, "bold"), bg="#1e293b", fg="#4ade80", padx=10, pady=8, relief="solid", bd=1)
        table_card.pack(fill="both", expand=True, pady=6)

        columns = ("app_name", "bundle_id", "device", "last_refresh", "remaining")
        self.tree = ttk.Treeview(table_card, columns=columns, show="headings", height=5)
        self.tree.heading("app_name", text="Tên Ứng Dụng")
        self.tree.heading("bundle_id", text="Bundle Identifier")
        self.tree.heading("device", text="iPhone Đã Cài")
        self.tree.heading("last_refresh", text="Lần Ký Gần Nhất")
        self.tree.heading("remaining", text="Hạn Còn Lại (7 Ngày)")

        self.tree.column("app_name", width=170, anchor="w")
        self.tree.column("bundle_id", width=220, anchor="w")
        self.tree.column("device", width=180, anchor="w")
        self.tree.column("last_refresh", width=150, anchor="center")
        self.tree.column("remaining", width=140, anchor="center")

        tree_scroll = ttk.Scrollbar(table_card, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", self.on_table_row_double_click)

        # 4. Control Action Buttons Bar (Dùng Custom Canvas Button)
        btn_bar = tk.Frame(main_box, bg="#0f172a")
        btn_bar.pack(fill="x", pady=8)

        # Nút Ký & Cài đặt ngay (Manual Refresh)
        self.refresh_btn = CustomButton(
            btn_bar, text="🚀 Ký & Cài đặt ngay (Manual Refresh)",
            bg_color="#0284c7", fg_color="#ffffff", hover_color="#0369a1",
            font=("Helvetica", 11, "bold"), height=40, command=self.run_manual_refresh
        )
        self.refresh_btn.pack(side="left", fill="x", expand=True, padx=4)

        # Nút Bật/Tắt LaunchAgent
        self.toggle_agent_btn = CustomButton(
            btn_bar, text="⚙️ Bật Chạy ngầm (4 ngày)",
            bg_color="#16a34a", fg_color="#ffffff", hover_color="#15803d",
            font=("Helvetica", 11, "bold"), height=40, command=self.toggle_launchagent
        )
        self.toggle_agent_btn.pack(side="left", fill="x", expand=True, padx=4)

        # Nút Gỡ App
        self.uninstall_btn = CustomButton(
            btn_bar, text="🗑️ Gỡ App trên iPhone",
            bg_color="#dc2626", fg_color="#ffffff", hover_color="#b91c1c",
            font=("Helvetica", 11, "bold"), height=40, command=self.uninstall_app_from_device
        )
        self.uninstall_btn.pack(side="left", fill="x", expand=True, padx=4)

        # 5. Log Console
        log_box = tk.LabelFrame(main_box, text="  Nhật ký tiến trình (Console Log)  ", font=("Helvetica", 11, "bold"), bg="#1e293b", fg="#cbd5e1", padx=6, pady=6, relief="solid", bd=1)
        log_box.pack(fill="both", expand=True, pady=4)

        self.log_text = tk.Text(log_box, wrap="word", height=6, bg="#020617", fg="#4ade80", insertbackground="#ffffff", font=("Menlo", 10), padx=8, pady=6, relief="flat")
        self.log_text.pack(side="left", fill="both", expand=True)

        log_scroll = ttk.Scrollbar(log_box, command=self.log_text.yview)
        log_scroll.pack(side="right", fill="y")
        self.log_text.config(yscrollcommand=log_scroll.set)

    def log(self, msg):
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def browse_ipa(self):
        file_selected = filedialog.askopenfilename(
            title="Chọn file IPA",
            filetypes=[("iOS App Package", "*.ipa"), ("All Files", "*.*")],
            initialdir=str(BASE_DIR / "bin")
        )
        if file_selected:
            self.ipa_path_var.set(file_selected)
            app_name, bundle_id = auto_refresh.get_ipa_metadata(Path(file_selected))
            if bundle_id:
                self.bundle_id_var.set(bundle_id)
                self.log(f"-> Đã tự động nhận diện: App '{app_name}' (Bundle ID: {bundle_id})")

    def load_config_values(self):
        try:
            config = auto_refresh.load_config()
            self.ipa_path_var.set(str(config.get("ipa_path", "bin/AppDiuCard.ipa")))
            self.bundle_id_var.set(config.get("bundle_id", ""))
            self.interval_var.set(str(config.get("refresh_interval_days", 5)))
        except Exception as e:
            self.log(f"[LỖI] Không tải được config: {e}")

    def save_config_values(self):
        try:
            config_path = BASE_DIR / "config.json"
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["ipa_path"] = self.ipa_path_var.get().strip()
            cfg["bundle_id"] = self.bundle_id_var.get().strip()
            cfg["refresh_interval_days"] = int(self.interval_var.get().strip() or "5")

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.log(f"[LỖI] Lưu config: {e}")

    def on_device_selected(self, event=None):
        selected_text = self.device_select_var.get()
        if not hasattr(self, "devices_map"):
            return
        udid = self.devices_map.get(selected_text, "")
        try:
            config_path = BASE_DIR / "config.json"
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg["device_udid"] = udid
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.log(f"-> Đã chọn thiết bị: {selected_text}")
        except Exception as e:
            self.log(f"[LỖI] Lưu thiết bị: {e}")

    def reload_devices_list(self):
        def worker():
            devices = auto_refresh.list_available_devices()
            self.devices_map = {"[Tự động] Chọn thiết bị Online đầu tiên": ""}
            combo_values = ["[Tự động] Chọn thiết bị Online đầu tiên"]

            cfg = auto_refresh.load_config()
            saved_udid = cfg.get("device_udid", "").strip()
            selected_display = combo_values[0]

            for d in devices:
                display_name = f"📱 {d['name']} ({d['model']}) - {d['status_text']}"
                self.devices_map[display_name] = d['udid']
                combo_values.append(display_name)
                if saved_udid and saved_udid == d['udid']:
                    selected_display = display_name

            def update_ui():
                self.device_combo['values'] = combo_values
                self.device_select_var.set(selected_display)
                self.log(f"Đã quét tìm thấy {len(devices)} thiết bị Apple.")

            self.root.after(0, update_ui)

        threading.Thread(target=worker, daemon=True).start()

    def reload_apps_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        records = auto_refresh.load_all_records()
        for k, rec in records.items():
            app_name = rec.get("app_name") or "Thẻ của Dịu"
            bundle_id = rec.get("bundle_id", "N/A")
            dev_name = rec.get("device_name", "")
            dev_model = rec.get("device_model", "")
            if dev_name and dev_model:
                device_str = f"{dev_name} ({dev_model})"
            elif dev_name:
                device_str = dev_name
            else:
                device_str = "iPhone"

            last_dt_str = rec.get("last_refresh_local", "N/A")
            
            _, remaining = auto_refresh.calculate_remaining(rec.get("last_refresh_time", ""))
            if remaining > 0:
                rem_str = f"🟢 Còn {remaining:.1f} ngày"
            elif remaining == -1.0:
                rem_str = "Chưa rõ"
            else:
                rem_str = f"🔴 Đã hết hạn ({abs(remaining):.1f} ngày)"

            self.tree.insert("", "end", values=(app_name, bundle_id, device_str, last_dt_str, rem_str))

    def on_table_row_double_click(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return
        vals = self.tree.item(selected_item[0], "values")
        if vals:
            self.bundle_id_var.set(vals[1])
            self.log(f"-> Đã chọn app từ bảng: {vals[0]} ({vals[1]})")

    def run_manual_refresh(self):
        self.save_config_values()
        self.refresh_btn.set_enabled(False)
        self.refresh_btn.set_text("⏳ Đang xử lý...", bg_color="#475569")
        self.log("\n============================================================")
        self.log("🚀 BẮT ĐẦU KÝ & CÀI ĐẶT (MANUAL REFRESH)...")
        self.log("============================================================")

        def worker():
            try:
                config = auto_refresh.load_config()
                device_info = auto_refresh.get_connected_device(config)
                if not device_info:
                    self.log("[LỖI] Không tìm thấy iPhone hoặc iPhone chưa sẵn sàng!")
                    self.log("👉 Vui lòng cắm cáp USB và MỞ KHÓA iPhone.")
                    messagebox.showwarning("Chưa kết nối", "Vui lòng cắm cáp kết nối và MỞ KHÓA iPhone của bạn!")
                    return

                self.log(f"1. Thiết bị mục tiêu: {device_info['name']} ({device_info['model']})")
                self.log("2. Tìm chứng chỉ Apple Development...")
                identity = auto_refresh.find_signing_identity(config)
                self.log(f"-> Chứng chỉ: {identity}")

                self.log("3. Re-sign gói IPA...")
                signed_ipa = auto_refresh.resign_ipa(config, identity)
                self.log(f"-> Đã ký thành công: {signed_ipa.name}")

                self.log(f"4. Cài đặt vào iPhone '{device_info['name']}'...")
                auto_refresh.install_ipa(signed_ipa, device_info, config.get("bundle_id"))
                self.log("-> CÀI ĐẶT THÀNH CÔNG VÀO IPHONE!")

                app_name, _ = auto_refresh.get_ipa_metadata(config["resolved_ipa_path"])
                auto_refresh.record_success_state(config, device_info, app_name)
                auto_refresh.send_macos_notification("Auto-Refresh IPA", f"Đã refresh thành công {app_name}!")

                self.log(f"\n🎉 HOÀN TẤT: Ứng dụng '{app_name}' đã được làm mới 7 ngày sử dụng!")
                messagebox.showinfo("Thành công", f"Đã cài đặt & làm mới 7 ngày thành công ứng dụng:\n{app_name}")

            except Exception as e:
                self.log(f"\n[LỖI TRONG TIẾN TRÌNH]: {e}")
                messagebox.showerror("Thất bại", f"Lỗi: {e}")
            finally:
                self.refresh_btn.set_enabled(True)
                self.refresh_btn.set_text("🚀 Ký & Cài đặt ngay (Manual Refresh)", bg_color="#0284c7")
                self.reload_apps_table()
                self.reload_devices_list()

        threading.Thread(target=worker, daemon=True).start()

    def uninstall_app_from_device(self):
        bundle_id = self.bundle_id_var.get().strip()
        if not bundle_id:
            messagebox.showwarning("Thiếu Bundle ID", "Vui lòng nhập Bundle ID của ứng dụng cần gỡ!")
            return

        confirm = messagebox.askyesno("Xác nhận gỡ app", f"Bạn có chắc muốn gỡ bỏ hoàn toàn ứng dụng:\n{bundle_id}\nkhỏi iPhone không?")
        if not confirm:
            return

        self.log(f"\n🗑️ Đang gửi lệnh gỡ app {bundle_id}...")

        def worker():
            try:
                config = auto_refresh.load_config()
                dev = auto_refresh.get_connected_device(config)
                if not dev:
                    messagebox.showerror("Lỗi", "Chưa kết nối iPhone.")
                    return

                cmd = ["xcrun", "devicectl", "device", "uninstall", "app", "--device", dev["udid"], bundle_id]
                auto_refresh.run_command(cmd)
                self.log(f" Đã gỡ bỏ thành công ứng dụng {bundle_id} khỏi {dev['name']}!")
                messagebox.showinfo("Thành công", f"Đã gỡ cài đặt app khỏi {dev['name']}.")
                
                records = auto_refresh.load_all_records()
                # Xóa tất cả các bản ghi có Bundle ID này
                keys_to_del = [k for k, v in records.items() if v.get("bundle_id") == bundle_id]
                for k in keys_to_del:
                    del records[k]
                auto_refresh.save_all_records(records)
                self.reload_apps_table()

                # Nếu không còn ứng dụng nào trong danh sách quản lý, tự động tắt LaunchAgent
                if len(records) == 0:
                    target_plist = Path.home() / "Library" / "LaunchAgents" / "com.user.autorefresh.ipa.plist"
                    subprocess.run(["launchctl", "unload", str(target_plist)], check=False)
                    if target_plist.exists():
                        target_plist.unlink()
                    self.toggle_agent_btn.set_text("⚙️ Bật Chạy ngầm (5 ngày)", bg_color="#16a34a")
                    self.log("ℹ️ Không còn ứng dụng nào được quản lý. Đã tự động tắt chạy ngầm khởi động!")

            except Exception as e:
                self.log(f"[LỖI GỠ APP]: {e}")
                messagebox.showerror("Lỗi", f"Không thể gỡ app: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def toggle_launchagent(self):
        plist_file = BASE_DIR / "com.user.autorefresh.ipa.plist"
        target_plist = Path.home() / "Library" / "LaunchAgents" / "com.user.autorefresh.ipa.plist"

        res = subprocess.run(["launchctl", "list"], capture_output=True, text=True)
        if "com.user.autorefresh.ipa" in res.stdout:
            subprocess.run(["launchctl", "unload", str(target_plist)], check=False)
            if target_plist.exists():
                target_plist.unlink()
            self.toggle_agent_btn.set_text("⚙️ Bật Chạy ngầm (5 ngày)", bg_color="#16a34a")
            self.log(" Đã tắt dịch vụ chạy ngầm LaunchAgent.")
            messagebox.showinfo("LaunchAgent", "Đã tắt dịch vụ chạy ngầm tự động.")
        else:
            target_plist.parent.mkdir(parents=True, exist_ok=True)
            import shutil
            shutil.copy2(plist_file, target_plist)
            subprocess.run(["launchctl", "unload", str(target_plist)], check=False)
            subprocess.run(["launchctl", "load", str(target_plist)], check=False)
            self.toggle_agent_btn.set_text("🛑 Tắt Chạy ngầm (LaunchAgent)", bg_color="#ea580c")
            self.log(" Đã kích hoạt chạy ngầm LaunchAgent (5 ngày/lần & khi mở máy).")
            messagebox.showinfo("LaunchAgent", "Đã bật chạy ngầm tự động thành công!")


def main():
    root = tk.Tk()
    app = ModernAppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()

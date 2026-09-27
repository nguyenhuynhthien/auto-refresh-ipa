# Auto-Refresh-IPA (macOS Automation)

Hệ thống tự động ký lại (re-sign) và cài đặt đè (update) file `.ipa` lên iPhone cá nhân định kỳ **4 ngày/lần** (hoặc kiểm tra ngay khi mở máy / thức dậy từ Sleep) nhằm duy trì chứng chỉ **Free Developer Apple ID (hạn 7 ngày)** mà **KHÔNG cần bất kỳ ứng dụng trung gian nào trên iPhone** (như AltStore hay SideStore).

---

## 🚀 Tính năng nổi bật

1. **Native macOS & Zero-Third-Party trên iPhone**: Sử dụng trực tiếp `codesign`, `security`, `xcrun devicectl`.
2. **Tự động nhận diện thiết bị**: Quét iPhone cắm qua cáp USB hoặc kết nối Wi-Fi có trạng thái sẵn sàng.
3. **Cài đặt đè giữ nguyên dữ liệu**: Trùng khớp `CFBundleIdentifier` giúp update phiên bản mà không tạo app mới hoặc làm mất dữ liệu người dùng.
4. **Cơ chế kiểm tra thông minh 4 ngày**:
   - Lưu trạng thái vào `last_refresh_state.json`.
   - Mỗi khi mở máy Macbook (từ shutdown hoặc sleep), `launchd` kích hoạt script kiểm tra. Nếu đủ 4 ngày và có iPhone kết nối, hệ thống tự động ký và nạp app. Nếu chưa đủ ngày, script nhẹ nhàng kết thúc.
5. **Bảo mật & Biến môi trường**: Đọc `APPLE_ID` và `APPLE_PASSWORD` qua file `.env`.
6. **Thông báo macOS**: Gửi Notification trực tiếp lên góc màn hình macOS khi refresh thành công hoặc khi cần kết nối iPhone.

---

## 📁 Cấu trúc thư mục

```text
Auto-Refresh-IPA/
├── .env                              # Lưu APPLE_ID, APPLE_PASSWORD
├── config.json                       # Cấu hình IPA, Bundle ID, Signing Certificate, chu kỳ ngày
├── auto_refresh.py                   # Script chính xử lý kiểm tra hạn, resign và install
├── com.user.autorefresh.ipa.plist    # Cấu hình macOS LaunchAgent
├── manage_service.sh                 # Script bash tiện ích (install / uninstall / run-now / status)
├── requirements.txt                  # Thư viện Python phụ thuộc (python-dotenv)
├── bin/
│   └── AppDiuCard.ipa                # File IPA nguồn
├── build/                            # Thư mục chứa IPA sau khi ký (tự động tạo)
└── logs/                             # Log chạy định kỳ và chi tiết lỗi
```

---

## 🛠️ Yêu cầu & Cài đặt

### 1. Cài đặt Python Dependencies
```bash
pip3 install -r requirements.txt
```

### 2. Cài đặt các công cụ bổ trợ (Tùy chọn nếu cần)
Hệ thống mặc định sử dụng `xcrun devicectl` (tích hợp sẵn trong Xcode Command Line Tools). Nếu muốn hỗ trợ thêm các giao tiếp khác, bạn có thể cài thêm:
```bash
# Cài đặt qua Homebrew (nếu cần)
brew install libimobiledevice ideviceinstaller

# Hoặc pymobiledevice3
pip3 install pymobiledevice3
```

---

## ⚙️ Cấu hình

### 1. File `.env`
Kiểm tra thông tin tài khoản Apple ID của bạn:
```env
APPLE_ID=victoriakzru@gmail.com
APPLE_PASSWORD=your_apple_password
```

### 2. File `config.json`
```json
{
  "ipa_path": "bin/AppDiuCard.ipa",
  "bundle_id": "com.nguyenhuynhthien.diucard2025",
  "signing_identity": "Apple Development: victoriakzru@gmail.com (JY83LRR7WU)",
  "team_id": "JY83LRR7WU",
  "provisioning_profile_path": "",
  "device_udid": "",
  "refresh_interval_days": 5,
  "state_file": "last_refresh_state.json",
  "install_method": "auto"
}
```

> **Ghi chú**: Nếu `signing_identity` hoặc `device_udid` để trống, script sẽ tự động tìm chứng chỉ khớp với `APPLE_ID` trong Keychain và thiết bị iPhone đang kết nối.

---

## 🖥️ Hướng dẫn sử dụng

### 1. Ứng dụng Thanh Menu macOS (Menu Bar App) ⚡
Bạn có thể cho ứng dụng chạy thường trực trên thanh Menu Bar trên cùng của macOS:
```bash
python3 menubar_app.py
# hoặc
./manage_service.sh menubar
```
**Trên thanh Menu Bar bạn có thể:**
- 📱 Xem nhanh danh sách iPhone (`Abc`, `Mochi 🌟`) và trạng thái Online/Offline.
- 📦 Xem danh sách tất cả các App và **số ngày còn hạn** theo thời gian thực (ví dụ: `🟢 Còn 6.8 ngày` hay `🔴 Hết hạn`).
- 🚀 Bấm **"🚀 Ký & Refresh ngay"** chỉ với 1 cú click chuột.
- 🖥️ Mở nhanh Dashboard GUI khi cần đổi file IPA hoặc cấu hình nâng cao.

---

### 2. Sử dụng Giao diện Đồ Họa Đầy Đủ (GUI Dashboard)
Khởi chạy giao diện trực quan:
```bash
python3 gui_app.py
# hoặc
./manage_service.sh gui
```
**Trên giao diện bạn có thể:**
- Chọn file IPA trực tiếp bằng File Dialog.
- Thay đổi Bundle ID, chu kỳ refresh (số ngày).
- Theo dõi trạng thái kết nối iPhone và hạn refresh.
- Bấm **"🚀 Ký & Cài đặt ngay (Manual Refresh)"** để cài lần đầu hoặc làm mới chứng chỉ ngay lập tức.
- Bấm **"⚙️ Cài đặt chạy ngầm (5 ngày)"** để bật/tắt LaunchAgent.
- Bấm **"🗑️ Gỡ App trên iPhone"** để xóa app khỏi iPhone mà không cần thao tác tay trên điện thoại.
- Xem log chi tiết từng bước theo thời gian thực.

---

### 2. Cài đặt lần đầu vào iPhone (Initial Install)
Nếu file IPA **chưa từng được cài trên iPhone**:
1. Cắm cáp kết nối iPhone với máy Mac, mở khóa màn hình iPhone (chọn *"Tin cậy máy tính này"* nếu có thông báo).
2. Chạy lệnh hoặc bấm nút trên GUI:
   ```bash
   ./manage_service.sh run-now
   ```
3. Lệnh này sẽ tự động:
   - Ký lại (Re-sign) file IPA bằng Apple ID của bạn.
   - Sử dụng `xcrun devicectl` đẩy file vào iPhone để cài mới hoàn toàn.
4. Trên iPhone, vào **Cài đặt > Cài đặt chung > Quản lý VPN & Thiết bị**, chọn Apple ID của bạn và bấm **"Tin cậy"** (chỉ cần làm 1 lần duy nhất cho thiết bị).

---

### 3. Làm mới thủ công bất cứ lúc nào (Manual Refresh)
Bất cứ khi nào bạn muốn refresh lại hạn 7 ngày mà không cần đợi lịch tự động:
```bash
./manage_service.sh run-now
# hoặc
python3 auto_refresh.py --force
```

---

### 4. Gỡ bỏ Hoàn toàn Hệ thống (Clean Uninstall)

Để gỡ bỏ sạch sẽ 100% hệ thống Auto-Refresh khỏi máy Mac (tắt chạy ngầm, xóa daemon khởi động cùng máy, dọn log và cache):

Chỉ cần chạy 1 script tự động:
```bash
./uninstall.sh
```

**Script `uninstall.sh` sẽ tự động thực hiện:**
1. Hủy và xóa `LaunchAgent` khỏi `~/Library/LaunchAgents/` (không còn tự chạy khi khởi động hay đánh thức MacBook).
2. Xóa sạch các thư mục `build/`, `logs/`, và file trạng thái `last_refresh_state.json`.
3. Tùy chọn gỡ luôn ứng dụng khỏi iPhone nếu bạn muốn.
4. Sau đó, bạn chỉ cần xóa thư mục dự án nếu không dùng nữa.

---

### 5. Kích hoạt chạy ngầm tự động định kỳ (LaunchAgent)
```bash
./manage_service.sh install
```

Kiểm tra trạng thái service:
```bash
./manage_service.sh status
```

---

## 📜 Xem Log
Toàn bộ log được ghi lại tại thư mục `logs/`:
- Log script chi tiết: `logs/auto_refresh.log`
- Log launchd stdout: `logs/launchd_stdout.log`
- Log launchd stderr: `logs/launchd_stderr.log`

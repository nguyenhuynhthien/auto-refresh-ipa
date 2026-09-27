#!/usr/bin/env python3
"""
Auto-Refresh-IPA: Quản lý tự động ký lại và nạp IPA lên nhiều thiết bị iOS.
Hỗ trợ kiểm tra thời hạn còn lại (Free 7 ngày), quản lý nhiều app trên nhiều thiết bị.
"""

import os
import sys
import json
import shutil
import logging
import argparse
import subprocess
import plistlib
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "auto_refresh.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("AutoRefreshIPA")

load_dotenv(BASE_DIR / ".env")


def run_command(cmd, check=True, capture_output=True, text=True, cwd=None, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=capture_output,
        text=text,
        cwd=cwd,
        env=merged_env
    )
    if check and result.returncode != 0:
        err_msg = result.stderr.strip() if result.stderr else result.stdout.strip()
        raise RuntimeError(f"Command failed ({' '.join(cmd) if isinstance(cmd, list) else cmd}): {err_msg}")
    return result


def load_config():
    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        logger.error(f"Không tìm thấy file cấu hình tại {config_path}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["apple_id"] = os.getenv("APPLE_ID") or config.get("apple_id", "")
    config["apple_password"] = os.getenv("APPLE_PASSWORD") or config.get("apple_password", "")

    ipa_path = Path(config.get("ipa_path", "bin/AppDiuCard.ipa"))
    if not ipa_path.is_absolute():
        ipa_path = BASE_DIR / ipa_path
    config["resolved_ipa_path"] = ipa_path

    state_file = Path(config.get("state_file", "last_refresh_state.json"))
    if not state_file.is_absolute():
        state_file = BASE_DIR / state_file
    config["resolved_state_file"] = state_file

    return config


def load_all_records():
    """Đọc toàn bộ lịch sử quản lý app/thiết bị từ last_refresh_state.json"""
    state_file = BASE_DIR / "last_refresh_state.json"
    if not state_file.exists():
        return {}
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Định dạng mới: {"records": { "<udid>_<bundle_id>": { ... } }}
            if isinstance(data, dict) and "records" in data:
                return data["records"]
            elif isinstance(data, dict) and "last_refresh_time" in data:
                # Chuyển đổi định dạng cũ sang mới
                k = f"{data.get('device', {}).get('udid', 'unknown')}_{data.get('bundle_id', 'unknown')}"
                return {k: data}
            return {}
    except Exception as e:
        logger.warning(f"Không đọc được state file: {e}")
        return {}


def save_all_records(records):
    state_file = BASE_DIR / "last_refresh_state.json"
    data = {"records": records}
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_record(udid, bundle_id):
    records = load_all_records()
    k = f"{udid}_{bundle_id}"
    return records.get(k)


def calculate_remaining(last_refresh_iso, total_validity_days=7.0):
    """Tính số ngày còn lại của chứng chỉ 7 ngày"""
    try:
        last_dt = datetime.fromisoformat(last_refresh_iso)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        now_dt = datetime.now(timezone.utc)
        passed_days = (now_dt - last_dt).total_seconds() / 86400.0
        remaining_days = total_validity_days - passed_days
        return passed_days, remaining_days
    except Exception:
        return 999.0, -1.0


def check_refresh_due(config, force=False):
    if force:
        return True

    interval_days = config.get("refresh_interval_days", 4)
    bundle_id = config.get("bundle_id", "")
    udid = config.get("device_udid", "")
    
    records = load_all_records()
    matched_record = None
    if udid:
        matched_record = records.get(f"{udid}_{bundle_id}")
    else:
        for k, v in records.items():
            if v.get("bundle_id") == bundle_id:
                matched_record = v
                break

    if not matched_record or "last_refresh_time" not in matched_record:
        logger.info("Chưa có lịch sử refresh cho app này. Cần refresh lần đầu.")
        return True

    passed_days, remaining = calculate_remaining(matched_record["last_refresh_time"])
    logger.info(f"Đã qua {passed_days:.2f} ngày. Còn lại: {remaining:.2f} ngày.")

    if passed_days >= interval_days or remaining <= 1.0:
        logger.info(f"Đã đến kỳ refresh định kỳ {interval_days} ngày!")
        return True
    return False


def record_success_state(config, device_info, app_display_name="App"):
    records = load_all_records()
    now_dt = datetime.now(timezone.utc)
    udid = device_info.get("udid", "auto")
    bundle_id = config.get("bundle_id", "")
    
    key = f"{udid}_{bundle_id}"
    records[key] = {
        "last_refresh_time": now_dt.isoformat(),
        "last_refresh_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "app_name": app_display_name,
        "bundle_id": bundle_id,
        "device_name": device_info.get("name", "iPhone"),
        "device_udid": udid,
        "device_model": device_info.get("model", "iPhone"),
        "ipa_source": str(config["resolved_ipa_path"])
    }
    save_all_records(records)
    logger.info(f"Đã ghi nhận trạng thái cho app {bundle_id} trên {device_info.get('name')}")


def list_available_devices():
    """Lấy danh sách tất cả iPhone vật lý với TÊN THIẾT BỊ và TRẠNG THÁI chính xác"""
    devices_list = []
    try:
        res = run_command(["xcrun", "devicectl", "list", "devices"], check=False)
        if res.returncode == 0:
            lines = res.stdout.strip().splitlines()
            # Bỏ qua header
            data_lines = [l for l in lines if l and not l.startswith("Name") and not l.startswith("----")]
            for line in data_lines:
                if "physical" in line.lower():
                    # Parse dòng dạng: Name | Hostname | Identifier | State | Model | Reality
                    parts = [p.strip() for p in line.split("   ") if p.strip()]
                    name = "iPhone"
                    udid = ""
                    state = ""
                    model = "iPhone"

                    # Tìm UDID
                    for p in parts:
                        if "(UDID)" in p:
                            udid = p.replace("(UDID)", "").strip()
                    
                    if len(parts) >= 1:
                        name = parts[0]
                    
                    # Xác định state & model
                    line_lower = line.lower()
                    is_available = "available" in line_lower and "unavailable" not in line_lower
                    
                    if "iphone 11" in line_lower:
                        model = "iPhone 11"
                    elif "iphone 15" in line_lower:
                        model = "iPhone 15"
                    elif "iphone 12" in line_lower:
                        model = "iPhone 12"
                    elif "iphone 13" in line_lower:
                        model = "iPhone 13"
                    elif "iphone 14" in line_lower:
                        model = "iPhone 14"
                    elif "iphone 16" in line_lower:
                        model = "iPhone 16"

                    status_text = "Online (Sẵn sàng)" if is_available else "Offline (Chưa kết nối)"
                    
                    if udid:
                        devices_list.append({
                            "name": name,
                            "udid": udid,
                            "model": model,
                            "is_ready": is_available,
                            "status_text": status_text,
                            "tool": "devicectl"
                        })
    except Exception as e:
        logger.debug(f"list_available_devices error: {e}")
    return devices_list


def get_connected_device(config):
    device_udid_config = config.get("device_udid", "").strip()
    all_devs = list_available_devices()
    
    if device_udid_config:
        for d in all_devs:
            if d["udid"] == device_udid_config:
                return d

    # Nếu không chỉ định, lấy máy online đầu tiên
    for d in all_devs:
        if d["is_ready"]:
            return d
            
    # Fallback nếu không có máy nào online
    if all_devs:
        return all_devs[0]
    return None


def find_signing_identity(config):
    specified = config.get("signing_identity", "").strip()
    res = run_command(["security", "find-identity", "-v", "-p", "codesigning"])
    output = res.stdout

    valid_identities = []
    for line in output.splitlines():
        line = line.strip()
        if ")" in line and '"' in line:
            parts = line.split('"', 2)
            if len(parts) >= 2:
                name = parts[1]
                valid_identities.append(name)

    if not valid_identities:
        raise RuntimeError("Không tìm thấy Apple Development Certificate trong Keychain!")

    if specified and specified in valid_identities:
        return specified

    apple_id = config.get("apple_id", "")
    if apple_id:
        for ident in valid_identities:
            if apple_id in ident:
                return ident

    return valid_identities[0]


def find_provisioning_profile(config, app_dir):
    configured_profile = config.get("provisioning_profile_path", "").strip()
    if configured_profile:
        p = Path(configured_profile)
        if not p.is_absolute():
            p = BASE_DIR / p
        if p.exists():
            return p

    xcode_profiles_dir = Path.home() / "Library" / "MobileDevice" / "Provisioning Profiles"
    if xcode_profiles_dir.exists():
        for prof in xcode_profiles_dir.glob("*.mobileprovision"):
            try:
                cmd = ["security", "cms", "-D", "-i", str(prof)]
                res = run_command(cmd, check=False)
                if res.returncode == 0:
                    plist_data = plistlib.loads(res.stdout.encode("utf-8"))
                    entitlements = plist_data.get("Entitlements", {})
                    app_id = entitlements.get("application-identifier", "")
                    if config.get("bundle_id") in app_id:
                        return prof
            except Exception:
                continue

    embedded_in_app = app_dir / "embedded.mobileprovision"
    if embedded_in_app.exists():
        return embedded_in_app

    return None


def get_ipa_metadata(ipa_path):
    """Trích xuất CFBundleDisplayName và CFBundleIdentifier từ file IPA"""
    try:
        with tempfile.TemporaryDirectory() as td:
            run_command(["unzip", "-q", "-j", str(ipa_path), "Payload/*.app/Info.plist", "-d", td], check=False)
            plist_file = Path(td) / "Info.plist"
            if plist_file.exists():
                with open(plist_file, "rb") as f:
                    pl = plistlib.load(f)
                app_name = pl.get("CFBundleDisplayName") or pl.get("CFBundleName") or ipa_path.stem
                bundle_id = pl.get("CFBundleIdentifier") or ""
                return app_name, bundle_id
    except Exception:
        pass
    return ipa_path.stem, ""


def resign_ipa(config, signing_identity):
    src_ipa = config["resolved_ipa_path"]
    if not src_ipa.exists():
        raise FileNotFoundError(f"File IPA không tồn tại: {src_ipa}")

    logger.info(f"Bắt đầu quá trình Re-sign file IPA: {src_ipa.name}")

    build_dir = BASE_DIR / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    temp_work_dir = Path(tempfile.mkdtemp(dir=build_dir, prefix="resign_"))
    output_ipa = BASE_DIR / "build" / f"signed_{src_ipa.name}"

    try:
        run_command(["unzip", "-q", "-o", str(src_ipa), "-d", str(temp_work_dir)])

        payload_dir = temp_work_dir / "Payload"
        if not payload_dir.exists():
            raise RuntimeError("Cấu trúc file IPA không hợp lệ (thiếu Payload)")

        app_dirs = list(payload_dir.glob("*.app"))
        if not app_dirs:
            raise RuntimeError("Không tìm thấy file .app bên trong Payload")
        app_dir = app_dirs[0]

        profile_path = find_provisioning_profile(config, app_dir)
        entitlements_file = temp_work_dir / "entitlements.plist"

        if profile_path and profile_path.exists():
            target_profile = app_dir / "embedded.mobileprovision"
            if profile_path != target_profile:
                shutil.copy2(profile_path, target_profile)
            
            cms_res = run_command(["security", "cms", "-D", "-i", str(target_profile)])
            plist_data = plistlib.loads(cms_res.stdout.encode("utf-8"))
            entitlements = plist_data.get("Entitlements", {})
            
            with open(entitlements_file, "wb") as f:
                plistlib.dump(entitlements, f)
        else:
            entitlements = {
                "get-task-allow": True,
                "application-identifier": f"{config.get('team_id', '')}.{config.get('bundle_id', '')}"
            }
            with open(entitlements_file, "wb") as f:
                plistlib.dump(entitlements, f)

        code_sig_dir = app_dir / "_CodeSignature"
        if code_sig_dir.exists():
            shutil.rmtree(code_sig_dir)

        frameworks_dir = app_dir / "Frameworks"
        if frameworks_dir.exists():
            for item in frameworks_dir.iterdir():
                if item.suffix in [".framework", ".dylib"]:
                    run_command([
                        "codesign", "--force", "--verify", "--verbose",
                        "--sign", signing_identity,
                        "--timestamp=none",
                        str(item)
                    ])

        plugins_dir = app_dir / "PlugIns"
        if plugins_dir.exists():
            for item in plugins_dir.glob("*.appex"):
                run_command([
                    "codesign", "--force", "--verify", "--verbose",
                    "--sign", signing_identity,
                    "--timestamp=none",
                    "--entitlements", str(entitlements_file),
                    str(item)
                ])

        run_command([
            "codesign", "--force", "--verify", "--verbose",
            "--sign", signing_identity,
            "--timestamp=none",
            "--entitlements", str(entitlements_file),
            str(app_dir)
        ])

        run_command(["codesign", "--verify", "--deep", "--strict", str(app_dir)])

        if output_ipa.exists():
            output_ipa.unlink()

        run_command(["zip", "-q", "-r", "-y", str(output_ipa), "Payload"], cwd=str(temp_work_dir))
        return output_ipa
    finally:
        if temp_work_dir.exists():
            shutil.rmtree(temp_work_dir, ignore_errors=True)


def install_ipa(signed_ipa_path, device_info, bundle_id):
    logger.info(f"Cài đặt {signed_ipa_path.name} lên: {device_info['name']} (UDID: {device_info['udid']})")
    cmd = ["xcrun", "devicectl", "device", "install", "app", "--device", device_info["udid"], str(signed_ipa_path)]
    run_command(cmd)
    logger.info("Cài đặt thành công!")


def send_macos_notification(title, message):
    try:
        script = f'display notification "{message}" with title "{title}" sound name "default"'
        subprocess.run(["osascript", "-e", script], check=False)
    except Exception:
        pass


def refresh_single_app(ipa_path, bundle_id, device_info, signing_identity, app_display_name):
    """Ký và cài đặt 1 ứng dụng cụ thể lên 1 thiết bị"""
    ipa_path = Path(ipa_path)
    if not ipa_path.is_absolute():
        ipa_path = BASE_DIR / ipa_path

    if not ipa_path.exists():
        logger.warning(f"File IPA không tồn tại: {ipa_path}")
        return False

    temp_cfg = {
        "resolved_ipa_path": ipa_path,
        "bundle_id": bundle_id,
        "team_id": signing_identity.split("(")[-1].replace(")", "").strip() if "(" in signing_identity else "",
        "provisioning_profile_path": ""
    }
    logger.info(f"==> Tiến hành Refresh App '{app_display_name}' ({bundle_id}) lên máy '{device_info['name']}'...")
    signed_ipa = resign_ipa(temp_cfg, signing_identity)
    install_ipa(signed_ipa, device_info, bundle_id)
    record_success_state(temp_cfg, device_info, app_display_name)
    logger.info(f"==> Hoàn tất Refresh '{app_display_name}' lên '{device_info['name']}'!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Tự động ký và làm mới IPA định kỳ cho tất cả các app đang quản lý")
    parser.add_argument("--force", action="store_true", help="Bỏ qua kiểm tra thời gian 5 ngày, ép buộc refresh ngay")
    parser.add_argument("--check-only", action="store_true", help="Chỉ kiểm tra tình trạng")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("BẮT ĐẦU QUY TRÌNH CHẠY NGẦM AUTO-REFRESH CHO TẤT CẢ ỨNG DỤNG")
    logger.info("=" * 60)

    try:
        config = load_config()
        interval_days = config.get("refresh_interval_days", 4)
        records = load_all_records()

        # Nếu chưa có danh sách records nào, thêm app hiện tại trong config vào quản lý
        if not records:
            app_name, b_id = get_ipa_metadata(config["resolved_ipa_path"])
            records["default_app"] = {
                "app_name": app_name or "iOS App",
                "bundle_id": config.get("bundle_id"),
                "device_name": "iPhone",
                "device_udid": config.get("device_udid", ""),
                "device_model": "iPhone",
                "ipa_source": str(config["resolved_ipa_path"]),
                "last_refresh_time": ""
            }

        available_devices = {d["udid"]: d for d in list_available_devices()}
        online_devices = [d for d in available_devices.values() if d["is_ready"]]

        signing_identity = None
        refreshed_count = 0

        for key, rec in records.items():
            app_name = rec.get("app_name", "App")
            bundle_id = rec.get("bundle_id", "")
            target_udid = rec.get("device_udid", "")
            ipa_source = rec.get("ipa_source", str(config["resolved_ipa_path"]))
            last_refresh = rec.get("last_refresh_time", "")

            # 1. Kiểm tra hạn
            passed_days, remaining = calculate_remaining(last_refresh)
            is_due = (passed_days >= interval_days) or (remaining <= 1.5) or args.force or not last_refresh

            logger.info(f"Kiểm tra [{app_name} | {bundle_id}]: Đã qua {passed_days:.1f} ngày, Còn lại: {remaining:.1f} ngày -> Cần refresh: {is_due}")

            if not is_due:
                continue

            if args.check_only:
                logger.info(f"App '{app_name}' đã đến hạn cần refresh.")
                continue

            # 2. Tìm thiết bị phù hợp (đang Online)
            target_dev = None
            if target_udid and target_udid in available_devices:
                dev_candidate = available_devices[target_udid]
                if dev_candidate["is_ready"]:
                    target_dev = dev_candidate
            
            # Fallback nếu thiết bị chưa cắm hoặc chọn chế độ auto
            if not target_dev and online_devices:
                target_dev = online_devices[0]

            if not target_dev:
                logger.warning(f"⚠️ Thiết bị cho app '{app_name}' chưa sẵn sàng (Chưa cắm cáp / Đang khóa màn hình). Sẽ thử lại lần sau.")
                continue

            # 3. Ký và cài đặt
            if not signing_identity:
                signing_identity = find_signing_identity(config)

            success = refresh_single_app(ipa_source, bundle_id, target_dev, signing_identity, app_name)
            if success:
                refreshed_count += 1
                send_macos_notification("Auto-Refresh IPA", f"Đã tự động làm mới 7 ngày cho app '{app_name}' trên {target_dev['name']}!")

        logger.info(f"Tổng kết quy trình: Đã refresh thành công {refreshed_count} ứng dụng.")

    except Exception as e:
        logger.exception(f"Lỗi quy trình chạy ngầm: {e}")
        send_macos_notification("Auto-Refresh IPA Lỗi", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()

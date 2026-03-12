#!/usr/bin/env python3
"""
frame.py — ADB wireless control for Muse Frames (Android smart glasses).

Commands:
  pair <ip:port> <pairing_code>   Pair with the device (one-time setup)
  connect <ip:port>               Connect to paired device
  disconnect                      Disconnect from device
  status                          Show connection status & device info
  push <local_file> <remote_path> Push a file to the device
  screen <image_path>             Display an image on the frames
  stream <video_path>             Stream a video to the frames
  open <url_or_file>              Open a URL or media file on device
  shell <command...>              Run an arbitrary ADB shell command
  apps                            List installed packages
  install <apk_path>              Install an APK
  screenshot [output_path]        Capture a screenshot from the device
"""

import subprocess
import sys
import os

ADB = os.environ.get("ADB_PATH", r"C:\Users\User\tools\platform-tools\adb.exe")
DEVICE = os.environ.get("FRAME_DEVICE", None)  # e.g. "192.168.1.173:35957"


def get_device_serial():
    """Auto-detect the connected device serial, or use DEVICE if set."""
    if DEVICE:
        return DEVICE
    # List devices and pick the first network (ip:port) device
    result = subprocess.run([ADB, "devices"], capture_output=True, text=True)
    for line in result.stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device" and ":" in parts[0]:
            return parts[0]
    return None


def run_adb(*args, capture=True):
    """Run an ADB command and return (returncode, stdout, stderr)."""
    serial = get_device_serial()
    cmd = [ADB]
    # Add -s for device-specific commands (not for pair/connect/disconnect/devices)
    if serial and args and args[0] not in ("pair", "connect", "disconnect", "devices"):
        cmd += ["-s", serial]
    cmd += list(args)
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    result = subprocess.run(cmd, capture_output=capture, text=True, env=env)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def pair(ip_port, code):
    """Pair with device using wireless debugging pairing code."""
    rc, out, err = run_adb("pair", ip_port, code)
    print(out or err)
    return rc


def connect(ip_port):
    """Connect to a paired device."""
    rc, out, err = run_adb("connect", ip_port)
    print(out or err)
    return rc


def disconnect():
    """Disconnect all devices."""
    rc, out, err = run_adb("disconnect")
    print(out or err)
    return rc


def status():
    """Show connected devices and device info."""
    rc, out, err = run_adb("devices", "-l")
    print(out or err)
    if "device " in out and "List" not in out.split("device")[0].split("\n")[-1]:
        # Get device model info
        rc2, model, _ = run_adb("shell", "getprop", "ro.product.model")
        rc3, android_ver, _ = run_adb("shell", "getprop", "ro.build.version.release")
        rc4, battery, _ = run_adb("shell", "dumpsys", "battery")
        if model:
            print(f"\nModel: {model}")
        if android_ver:
            print(f"Android: {android_ver}")
        if battery:
            for line in battery.split("\n"):
                if "level" in line.lower():
                    print(f"Battery: {line.strip()}")
                    break
    return rc


def push_file(local_path, remote_path):
    """Push a file to the device."""
    rc, out, err = run_adb("push", local_path, remote_path)
    print(out or err)
    return rc


def screen(image_path):
    """Push an image and display it on the device."""
    filename = os.path.basename(image_path)
    remote = f"/sdcard/Download/{filename}"
    rc, out, err = run_adb("push", image_path, remote)
    if rc != 0:
        print(f"Failed to push: {err}")
        return rc
    print(f"Pushed to {remote}")
    # Open with default image viewer via intent
    rc2, out2, err2 = run_adb(
        "shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", f"file://{remote}", "-t", "image/*"
    )
    print(out2 or err2)
    return rc2


def stream(video_path):
    """Push a video and play it on the device."""
    filename = os.path.basename(video_path)
    remote = f"/sdcard/Download/{filename}"
    rc, out, err = run_adb("push", video_path, remote)
    if rc != 0:
        print(f"Failed to push: {err}")
        return rc
    print(f"Pushed to {remote}")
    # Open with default video player
    rc2, out2, err2 = run_adb(
        "shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", f"file://{remote}", "-t", "video/*"
    )
    print(out2 or err2)
    return rc2


def open_content(uri):
    """Open a URL or content URI on the device."""
    mime = "text/html"
    if uri.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
        mime = "image/*"
    elif uri.endswith((".mp4", ".mkv", ".avi", ".webm", ".mov")):
        mime = "video/*"
    elif uri.endswith((".mp3", ".wav", ".ogg", ".flac", ".aac")):
        mime = "audio/*"

    rc, out, err = run_adb(
        "shell", "am", "start", "-a", "android.intent.action.VIEW",
        "-d", uri, "-t", mime
    )
    print(out or err)
    return rc


def shell(*cmd):
    """Run an arbitrary shell command on the device."""
    rc, out, err = run_adb("shell", *cmd)
    print(out or err)
    return rc


def apps():
    """List installed packages."""
    rc, out, err = run_adb("shell", "pm", "list", "packages", "-3")
    if out:
        for line in sorted(out.split("\n")):
            print(line.replace("package:", "  "))
    else:
        print(err or "No packages found")
    return rc


def install(apk_path):
    """Install an APK."""
    rc, out, err = run_adb("install", "-r", apk_path)
    print(out or err)
    return rc


def screenshot(output_path=None):
    """Capture screenshot from device."""
    if not output_path:
        output_path = "frame_screenshot.png"
    remote = "/sdcard/screenshot_tmp.png"
    run_adb("shell", "screencap", "-p", remote)
    rc, out, err = run_adb("pull", remote, output_path)
    run_adb("shell", "rm", remote)
    if rc == 0:
        print(f"Screenshot saved to {output_path}")
    else:
        print(f"Failed: {err}")
    return rc


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    cmd = sys.argv[1].lower()
    args = sys.argv[2:]

    commands = {
        "pair": lambda: pair(args[0], args[1]) if len(args) >= 2 else print("Usage: pair <ip:port> <code>"),
        "connect": lambda: connect(args[0]) if args else print("Usage: connect <ip:port>"),
        "disconnect": lambda: disconnect(),
        "status": lambda: status(),
        "push": lambda: push_file(args[0], args[1]) if len(args) >= 2 else print("Usage: push <local> <remote>"),
        "screen": lambda: screen(args[0]) if args else print("Usage: screen <image_path>"),
        "stream": lambda: stream(args[0]) if args else print("Usage: stream <video_path>"),
        "open": lambda: open_content(args[0]) if args else print("Usage: open <url_or_file>"),
        "shell": lambda: shell(*args) if args else print("Usage: shell <command...>"),
        "apps": lambda: apps(),
        "install": lambda: install(args[0]) if args else print("Usage: install <apk_path>"),
        "screenshot": lambda: screenshot(args[0] if args else None),
    }

    if cmd in commands:
        return commands[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)
        return 1


if __name__ == "__main__":
    sys.exit(main() or 0)

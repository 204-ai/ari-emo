---
name: frame
description: Control Muse Frames smart glasses via ADB wireless connection
user_invocable: true
arguments:
  - name: action
    description: "Action to perform: pair, connect, disconnect, status, screen, stream, open, shell, apps, install, screenshot, or push"
    required: true
---

# Frame Skill — ADB Wireless Control for Muse Frames

Control Muse Frames (Android smart glasses) over WiFi using ADB.

## Setup
- ADB installed at: `C:\Users\User\tools\platform-tools\adb.exe`
- Both devices must be on the same WiFi network
- Android 11+ required for wireless pairing

## How the Two-Step Handshake Works
1. **Pair** (one-time): Exchange security credentials using a pairing code from the device
2. **Connect**: Establish the data stream for sending commands

## Instructions

Parse the user's `$ARGUMENTS_ACTION` to determine what to do. The action may include additional details like IP addresses, file paths, or commands.

### Pair (one-time setup)
Ask the user for:
- The **IP address and port** shown in the wireless debugging pairing dialog on the Muse Frames
- The **6-digit pairing code** shown on the device

Then run:
```bash
python skills/camera/frame.py pair <ip:port> <pairing_code>
```

### Connect
Ask the user for the **IP address and port** shown in the wireless debugging settings (this is different from the pairing port).

```bash
python skills/camera/frame.py connect <ip:port>
```

### Disconnect
```bash
python skills/camera/frame.py disconnect
```

### Status
Check connection status and device info:
```bash
python skills/camera/frame.py status
```

### Screen (display an image)
Push an image file and display it on the frames:
```bash
python skills/camera/frame.py screen <path_to_image>
```

### Stream (play a video)
Push a video file and play it on the frames:
```bash
python skills/camera/frame.py stream <path_to_video>
```

### Open (URL or media)
Open a URL or content URI on the device:
```bash
python skills/camera/frame.py open <url_or_file_uri>
```

### Shell (run commands)
Run arbitrary ADB shell commands:
```bash
python skills/camera/frame.py shell <command>
```

### Apps (list installed)
```bash
python skills/camera/frame.py apps
```

### Install (APK)
```bash
python skills/camera/frame.py install <path_to_apk>
```

### Screenshot
Capture what's on the frames' display:
```bash
python skills/camera/frame.py screenshot [output_filename]
```

### Push (transfer files)
```bash
python skills/camera/frame.py push <local_file> <remote_path>
```

## After Running

- Report the result to the user clearly
- If a connection fails, suggest checking that:
  1. Wireless debugging is enabled on the Muse Frames
  2. Both devices are on the same WiFi network
  3. The IP/port is correct (ports change between pairing sessions)
- Set emotion to `happy` on success, `confused` on failure

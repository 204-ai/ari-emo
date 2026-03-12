Capture a photo from a connected camera.

## Available cameras
- **orbecc** — Orbecc Femto Bolt RGB (1920x1080, default)
- **c920** — Logitech HD Pro Webcam C920
- **ndi** — NDI network source (default IP: 192.168.1.188)

## Usage

Based on the user's request: $ARGUMENTS

Run the appropriate capture command:

```bash
# Default (Orbecc RGB)
python skills/camera/cam.py

# Specific camera
python skills/camera/cam.py --cam c920
python skills/camera/cam.py --cam orbecc
python skills/camera/cam.py --cam ndi
python skills/camera/cam.py --cam ndi --ndi-ip 192.168.1.100

# Custom output name
python skills/camera/cam.py --output my_photo.png
```

After capturing, show the image to the user with:
```
![Camera snap](/api/image?file=FILENAME)
```

The capture script handles sensor warmup automatically (important for the Orbecc Femto Bolt).
NDI capture connects to the network source via the NDI SDK DLL and handles UYVY/BGRA/RGBA pixel formats.

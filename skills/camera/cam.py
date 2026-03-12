"""
Camera Capture — Snap photos from connected cameras.

Available cameras:
  - orbecc:  Orbecc Femto Bolt RGB, 1920x1080, Media Foundation
  - c920:    Logitech HD Pro Webcam C920, DirectShow
  - ndi:     NDI network source (e.g. AIDA NDI POV at 192.168.1.188)

Usage:
  python cam.py                        # snap from Orbecc RGB (default)
  python cam.py --cam c920             # snap from Logitech C920
  python cam.py --cam ndi              # snap from NDI source
  python cam.py --cam ndi --ndi-ip 192.168.1.188  # NDI with specific IP
  python cam.py --cam 0                # snap by index
  python cam.py --output my_photo.png  # custom output filename
"""

import argparse
import sys
import time
from pathlib import Path

GENERATED = Path(__file__).resolve().parent.parent.parent / "generated"
GENERATED.mkdir(exist_ok=True)

# Camera presets: name -> (index, backend, width, height)
CAMERAS = {
    "orbecc": (1, "msmf", 1920, 1080),
    "c920":   (0, "dshow", 1920, 1080),
}

DEFAULT_CAMERA = "orbecc"
DEFAULT_NDI_IP = "192.168.1.188"
NDI_DLL = r"C:\Program Files\NDI\NDI 6 SDK\Bin\x64\Processing.NDI.Lib.x64.dll"


def snap(cam_index: int, backend: str, width: int, height: int,
         output: str, warmup_frames: int = 10) -> Path:
    """Capture a single frame from an OpenCV camera."""
    import cv2

    backend_flag = cv2.CAP_MSMF if backend == "msmf" else cv2.CAP_DSHOW
    cap = cv2.VideoCapture(cam_index, backend_flag)

    if not cap.isOpened():
        print(f"Error: Could not open camera {cam_index} with {backend} backend")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    # Warm up: read several frames to let sensor adjust
    frame = None
    for i in range(warmup_frames):
        ret, frame = cap.read()
        if ret and frame is not None and frame.mean() > 1:
            if i >= 3:
                break

    # Final capture
    for _ in range(3):
        ret, frame = cap.read()

    cap.release()

    if frame is None or not ret:
        print("Error: Failed to capture frame")
        sys.exit(1)

    h, w = frame.shape[:2]
    dest = GENERATED / output
    cv2.imwrite(str(dest), frame)
    print(f"Captured: {w}x{h} -> {dest}")
    return dest


def snap_ndi(output: str, target_ip: str = DEFAULT_NDI_IP,
             timeout_sec: int = 15) -> Path:
    """Capture a single frame from an NDI network source."""
    import ctypes
    import numpy as np
    from PIL import Image

    class NDIlib_find_create_t(ctypes.Structure):
        _fields_ = [
            ("show_local_sources", ctypes.c_bool),
            ("p_groups", ctypes.c_char_p),
            ("p_extra_ips", ctypes.c_char_p),
        ]

    class NDIlib_source_t(ctypes.Structure):
        _fields_ = [
            ("p_ndi_name", ctypes.c_char_p),
            ("p_url_address", ctypes.c_char_p),
        ]

    class NDIlib_recv_create_v3_t(ctypes.Structure):
        _fields_ = [
            ("source_to_connect_to", NDIlib_source_t),
            ("color_format", ctypes.c_int),
            ("bandwidth", ctypes.c_int),
            ("allow_video_fields", ctypes.c_bool),
            ("p_ndi_recv_name", ctypes.c_char_p),
        ]

    class NDIlib_video_frame_v2_t(ctypes.Structure):
        _fields_ = [
            ("xres", ctypes.c_int),
            ("yres", ctypes.c_int),
            ("FourCC", ctypes.c_int),
            ("frame_rate_N", ctypes.c_int),
            ("frame_rate_D", ctypes.c_int),
            ("picture_aspect_ratio", ctypes.c_float),
            ("frame_format_type", ctypes.c_int),
            ("timecode", ctypes.c_int64),
            ("p_data", ctypes.c_void_p),
            ("line_stride_in_bytes", ctypes.c_int),
            ("p_metadata", ctypes.c_char_p),
            ("timestamp", ctypes.c_int64),
        ]

    ndi = ctypes.CDLL(NDI_DLL)

    ndi.NDIlib_initialize.restype = ctypes.c_bool
    ndi.NDIlib_initialize.argtypes = []
    ndi.NDIlib_find_create_v2.restype = ctypes.c_void_p
    ndi.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(NDIlib_find_create_t)]
    ndi.NDIlib_find_wait_for_sources.restype = ctypes.c_bool
    ndi.NDIlib_find_wait_for_sources.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ndi.NDIlib_find_get_current_sources.restype = ctypes.POINTER(NDIlib_source_t)
    ndi.NDIlib_find_get_current_sources.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    ndi.NDIlib_recv_create_v3.restype = ctypes.c_void_p
    ndi.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(NDIlib_recv_create_v3_t)]
    ndi.NDIlib_recv_capture_v3.restype = ctypes.c_int
    ndi.NDIlib_recv_capture_v3.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(NDIlib_video_frame_v2_t),
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
    ]
    ndi.NDIlib_recv_free_video_v2.restype = None
    ndi.NDIlib_recv_free_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_video_frame_v2_t)]
    ndi.NDIlib_recv_destroy.restype = None
    ndi.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]
    ndi.NDIlib_find_destroy.restype = None
    ndi.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]
    ndi.NDIlib_destroy.restype = None
    ndi.NDIlib_destroy.argtypes = []

    if not ndi.NDIlib_initialize():
        print("Error: NDI init failed")
        sys.exit(1)

    find_create = NDIlib_find_create_t(True, None, target_ip.encode())
    finder = ndi.NDIlib_find_create_v2(ctypes.byref(find_create))
    if not finder:
        print("Error: Could not create NDI finder")
        ndi.NDIlib_destroy()
        sys.exit(1)

    print(f"Searching for NDI sources (target: {target_ip})...")
    source_name = source_url = None
    deadline = time.time() + timeout_sec

    while time.time() < deadline:
        ndi.NDIlib_find_wait_for_sources(finder, 2000)
        num = ctypes.c_uint32(0)
        sources_ptr = ndi.NDIlib_find_get_current_sources(finder, ctypes.byref(num))
        if num.value > 0:
            for i in range(num.value):
                name = sources_ptr[i].p_ndi_name.decode() if sources_ptr[i].p_ndi_name else ""
                url = sources_ptr[i].p_url_address.decode() if sources_ptr[i].p_url_address else ""
                print(f"  Found: {name} @ {url}")
                if target_ip in url or target_ip in name:
                    source_name = sources_ptr[i].p_ndi_name
                    source_url = sources_ptr[i].p_url_address
                    break
            if source_name:
                break
            source_name = sources_ptr[0].p_ndi_name
            source_url = sources_ptr[0].p_url_address
            break

    if not source_name:
        print("Error: No NDI source found")
        ndi.NDIlib_find_destroy(finder)
        ndi.NDIlib_destroy()
        sys.exit(1)

    print(f"Connecting to: {source_name.decode()}")

    recv_create = NDIlib_recv_create_v3_t()
    recv_create.source_to_connect_to.p_ndi_name = source_name
    recv_create.source_to_connect_to.p_url_address = source_url
    recv_create.color_format = 1  # BGRX_BGRA
    recv_create.bandwidth = 0
    recv_create.allow_video_fields = True
    recv_create.p_ndi_recv_name = b"AriCapture"

    receiver = ndi.NDIlib_recv_create_v3(ctypes.byref(recv_create))
    if not receiver:
        print("Error: Could not create NDI receiver")
        ndi.NDIlib_find_destroy(finder)
        ndi.NDIlib_destroy()
        sys.exit(1)

    ndi.NDIlib_find_destroy(finder)

    video_frame = NDIlib_video_frame_v2_t()
    dest = GENERATED / output

    UYVY, BGRA, BGRX, RGBA = 0x59565955, 0x41524742, 0x58524742, 0x41424752

    for _ in range(60):
        frame_type = ndi.NDIlib_recv_capture_v3(
            receiver, ctypes.byref(video_frame), None, None, 1000
        )
        if frame_type != 1:  # not video
            continue

        w, h = video_frame.xres, video_frame.yres
        fourcc = video_frame.FourCC
        stride = video_frame.line_stride_in_bytes

        if stride <= 0 or w <= 0 or h <= 0:
            ndi.NDIlib_recv_free_video_v2(receiver, ctypes.byref(video_frame))
            continue

        buf = (ctypes.c_uint8 * (stride * h))()
        ctypes.memmove(buf, video_frame.p_data, stride * h)
        data = bytes(buf)

        if fourcc in (BGRA, BGRX):
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, stride // 4, 4)[:, :w, :]
            rgb = arr[:, :, 2::-1].copy()
            img = Image.fromarray(rgb)
        elif fourcc == UYVY:
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w * 2)
            yuv = np.zeros((h, w, 3), dtype=np.float32)
            yuv[:, 0::2, 0] = arr[:, 1::4]
            yuv[:, 1::2, 0] = arr[:, 3::4]
            yuv[:, 0::2, 1] = arr[:, 0::4]
            yuv[:, 1::2, 1] = arr[:, 0::4]
            yuv[:, 0::2, 2] = arr[:, 2::4]
            yuv[:, 1::2, 2] = arr[:, 2::4]
            r = yuv[:,:,0] + 1.402 * (yuv[:,:,2] - 128)
            g = yuv[:,:,0] - 0.344136 * (yuv[:,:,1] - 128) - 0.714136 * (yuv[:,:,2] - 128)
            b = yuv[:,:,0] + 1.772 * (yuv[:,:,1] - 128)
            rgb = np.clip(np.stack([r,g,b], axis=2), 0, 255).astype(np.uint8)
            img = Image.fromarray(rgb)
        elif fourcc == RGBA:
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, stride // 4, 4)[:, :w, :]
            img = Image.fromarray(arr[:, :, :3])
        else:
            bpp = stride // w
            arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w, bpp)
            rgb = arr[:, :, 2::-1].copy()
            img = Image.fromarray(rgb)

        img.save(str(dest), quality=92)
        print(f"Captured: {w}x{h} -> {dest}")
        ndi.NDIlib_recv_free_video_v2(receiver, ctypes.byref(video_frame))
        ndi.NDIlib_recv_destroy(receiver)
        ndi.NDIlib_destroy()
        return dest

    print("Error: No video frame received from NDI source")
    ndi.NDIlib_recv_destroy(receiver)
    ndi.NDIlib_destroy()
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Capture a photo from a connected camera")
    parser.add_argument("--cam", "-c", default=DEFAULT_CAMERA,
                        help="Camera name (orbecc, c920, ndi) or index (0, 1, ...)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output filename (in generated/)")
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=10,
                        help="Number of warmup frames (default: 10)")
    parser.add_argument("--backend", "-b", default=None,
                        help="OpenCV backend: msmf or dshow")
    parser.add_argument("--ndi-ip", default=DEFAULT_NDI_IP,
                        help=f"NDI source IP (default: {DEFAULT_NDI_IP})")
    args = parser.parse_args()

    # NDI camera
    if args.cam == "ndi":
        output = args.output or f"ndi_snap_{int(time.time())}.jpg"
        print(f"Capturing from NDI source at {args.ndi_ip}...")
        dest = snap_ndi(output, target_ip=args.ndi_ip)
        print(f"\n![Camera snap](/api/image?file={output})")
        return 0

    # OpenCV cameras
    if args.cam in CAMERAS:
        cam_index, backend, w, h = CAMERAS[args.cam]
        cam_name = args.cam
    elif args.cam.isdigit():
        cam_index = int(args.cam)
        backend = "msmf"
        w, h = 1920, 1080
        cam_name = f"cam{cam_index}"
    else:
        print(f"Error: Unknown camera '{args.cam}'. Available: {', '.join(CAMERAS.keys())}, ndi")
        sys.exit(1)

    if args.width: w = args.width
    if args.height: h = args.height
    if args.backend: backend = args.backend

    output = args.output or f"{cam_name}_snap_{int(time.time())}.png"

    print(f"Capturing from {cam_name} (index {cam_index}, {backend}, {w}x{h})...")
    dest = snap(cam_index, backend, w, h, output, args.warmup)
    print(f"\n![Camera snap](/api/image?file={output})")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)

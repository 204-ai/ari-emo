"""Capture a single frame from an NDI source and save as JPEG."""
import ctypes
import ctypes.wintypes
import sys
import time
import numpy as np
from PIL import Image

NDI_DLL = r"C:\Program Files\NDI\NDI 6 SDK\Bin\x64\Processing.NDI.Lib.x64.dll"


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


def capture(output_path="ndi_snapshot.jpg", timeout_sec=15, target_ip="192.168.1.188"):
    ndi = ctypes.CDLL(NDI_DLL)

    # Set function signatures
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
        ctypes.c_void_p,
        ctypes.POINTER(NDIlib_video_frame_v2_t),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]

    ndi.NDIlib_recv_free_video_v2.restype = None
    ndi.NDIlib_recv_free_video_v2.argtypes = [ctypes.c_void_p, ctypes.POINTER(NDIlib_video_frame_v2_t)]

    ndi.NDIlib_recv_destroy.restype = None
    ndi.NDIlib_recv_destroy.argtypes = [ctypes.c_void_p]

    ndi.NDIlib_find_destroy.restype = None
    ndi.NDIlib_find_destroy.argtypes = [ctypes.c_void_p]

    ndi.NDIlib_destroy.restype = None
    ndi.NDIlib_destroy.argtypes = []

    # Initialize
    if not ndi.NDIlib_initialize():
        print("ERROR: NDI init failed")
        return False

    # Find sources
    find_create = NDIlib_find_create_t(True, None, target_ip.encode())
    finder = ndi.NDIlib_find_create_v2(ctypes.byref(find_create))
    if not finder:
        print("ERROR: Could not create finder")
        ndi.NDIlib_destroy()
        return False

    print(f"Searching for NDI sources (target: {target_ip})...")
    source_name = None
    source_url = None
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
            # Use first if no exact match
            source_name = sources_ptr[0].p_ndi_name
            source_url = sources_ptr[0].p_url_address
            break

    if not source_name:
        print("ERROR: No NDI source found")
        ndi.NDIlib_find_destroy(finder)
        ndi.NDIlib_destroy()
        return False

    print(f"Connecting to: {source_name.decode()}")

    # Create receiver - request BGRX/BGRA
    recv_create = NDIlib_recv_create_v3_t()
    recv_create.source_to_connect_to.p_ndi_name = source_name
    recv_create.source_to_connect_to.p_url_address = source_url
    recv_create.color_format = 1  # BGRX_BGRA
    recv_create.bandwidth = 0     # highest
    recv_create.allow_video_fields = True
    recv_create.p_ndi_recv_name = b"AriCapture"

    receiver = ndi.NDIlib_recv_create_v3(ctypes.byref(recv_create))
    if not receiver:
        print("ERROR: Could not create receiver")
        ndi.NDIlib_find_destroy(finder)
        ndi.NDIlib_destroy()
        return False

    # Don't need finder anymore
    ndi.NDIlib_find_destroy(finder)

    # Capture frames
    video_frame = NDIlib_video_frame_v2_t()
    captured = False

    for attempt in range(60):
        frame_type = ndi.NDIlib_recv_capture_v3(
            receiver, ctypes.byref(video_frame), None, None, 1000
        )
        if frame_type == 1:  # video
            w, h = video_frame.xres, video_frame.yres
            fourcc = video_frame.FourCC
            stride = video_frame.line_stride_in_bytes
            print(f"  Frame: {w}x{h}, FourCC=0x{fourcc:08X}, stride={stride}")

            if stride <= 0 or w <= 0 or h <= 0:
                ndi.NDIlib_recv_free_video_v2(receiver, ctypes.byref(video_frame))
                continue

            buf_size = stride * h
            raw = (ctypes.c_uint8 * buf_size)()
            ctypes.memmove(raw, video_frame.p_data, buf_size)
            data = bytes(raw)

            UYVY = 0x59565955
            BGRA = 0x41524742
            BGRX = 0x58524742
            RGBA = 0x41424752

            if fourcc in (BGRA, BGRX):
                arr = np.frombuffer(data, dtype=np.uint8).reshape(h, stride // 4, 4)[:, :w, :]
                rgb = arr[:, :, 2::-1].copy()  # BGR -> RGB
                img = Image.fromarray(rgb)
            elif fourcc == UYVY:
                # Pillow doesn't do UYVY directly, manual conversion
                arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w * 2)
                yuv = np.zeros((h, w, 3), dtype=np.float32)
                yuv[:, 0::2, 0] = arr[:, 1::4]  # Y0
                yuv[:, 1::2, 0] = arr[:, 3::4]  # Y1
                yuv[:, 0::2, 1] = arr[:, 0::4]  # U
                yuv[:, 1::2, 1] = arr[:, 0::4]  # U
                yuv[:, 0::2, 2] = arr[:, 2::4]  # V
                yuv[:, 1::2, 2] = arr[:, 2::4]  # V
                r = yuv[:,:,0] + 1.402 * (yuv[:,:,2] - 128)
                g = yuv[:,:,0] - 0.344136 * (yuv[:,:,1] - 128) - 0.714136 * (yuv[:,:,2] - 128)
                b = yuv[:,:,0] + 1.772 * (yuv[:,:,1] - 128)
                rgb = np.clip(np.stack([r,g,b], axis=2), 0, 255).astype(np.uint8)
                img = Image.fromarray(rgb)
            elif fourcc == RGBA:
                arr = np.frombuffer(data, dtype=np.uint8).reshape(h, stride // 4, 4)[:, :w, :]
                img = Image.fromarray(arr[:, :, :3])
            else:
                print(f"  Unknown FourCC 0x{fourcc:08X}, attempting BGRA decode...")
                bpp = stride // w
                arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w, bpp)
                rgb = arr[:, :, 2::-1].copy()
                img = Image.fromarray(rgb)

            img.save(output_path, quality=92)
            print(f"  Saved: {output_path} ({img.size[0]}x{img.size[1]})")
            captured = True
            ndi.NDIlib_recv_free_video_v2(receiver, ctypes.byref(video_frame))
            break

    ndi.NDIlib_recv_destroy(receiver)
    ndi.NDIlib_destroy()
    return captured


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "ndi_snapshot.jpg"
    ok = capture(out)
    sys.exit(0 if ok else 1)

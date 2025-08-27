# send_static_fixed.py
import time
import numpy as np
import cv2
import NDIlib as ndi

SENDER_NAME = "WSL Static Sender"
IMAGE_PATH  = "test.png"  # point to a real image

def main():
    if not ndi.initialize():
        raise RuntimeError("NDI init failed")

    sc = ndi.SendCreate()
    sc.ndi_name = SENDER_NAME          # <- correct field for your build
    if hasattr(sc, "clock_video"): sc.clock_video = True
    if hasattr(sc, "clock_audio"): sc.clock_audio = False

    sender = ndi.send_create(sc)
    if sender is None:
        raise RuntimeError("send_create failed")

    # Load and convert to BGRA
    bgr = cv2.imread(IMAGE_PATH, cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"Failed to read image: {IMAGE_PATH}")
    h, w = bgr.shape[:2]
    bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
    if not bgra.flags["C_CONTIGUOUS"]:
        bgra = np.ascontiguousarray(bgra)
    stride = bgra.strides[0]            # bytes per row

    # Describe frame
    vf = ndi.VideoFrameV2()
    vf.xres = w
    vf.yres = h
    vf.FourCC = ndi.FOURCC_VIDEO_TYPE_BGRA
    vf.frame_rate_N = 30000             # 30.000 fps
    vf.frame_rate_D = 1000
    vf.picture_aspect_ratio = w / float(h)
    vf.frame_format_type = ndi.FRAME_FORMAT_TYPE_PROGRESSIVE
    vf.line_stride_in_bytes = stride
    # Don’t set timecode; your build can synthesize if unset
    # vf.timecode = ndi.TIMECODE_SYNTHESIZE

    # IMPORTANT: pass the ndarray, not a pointer
    vf.data = bgra

    try:
        print(f"Sending {w}x{h} static frame as '{SENDER_NAME}' (Ctrl+C to stop)")
        while True:
            ndi.send_send_video_v2(sender, vf)
            time.sleep(1/30)
    except KeyboardInterrupt:
        pass
    finally:
        ndi.send_destroy(sender)
        ndi.destroy()

if __name__ == "__main__":
    main()

# recv_once.py
import time
import numpy as np
import cv2
import NDIlib as ndi

MATCH = "WSL Static Sender"  # substring of your sender's name

def video_frame_to_bgr(v):
    h, w = v.yres, v.xres
    stride = v.line_stride_in_bytes  # bytes per row

    # Grab bytes from whatever 'v.data' is (numpy array or buffer)
    data = v.data
    if isinstance(data, np.ndarray):
        # Ensure we have a 1D uint8 view over the full buffer
        arr = data.view(np.uint8).reshape(h, stride // 1)  # rows × bytes
    else:
        mv = memoryview(data)  # generic buffer interface
        arr = np.frombuffer(mv, dtype=np.uint8, count=h * stride).reshape(h, stride)

    # Interpret as BGRA (4 bytes per pixel), crop to width
    row_pixels = stride // 4
    bgra = arr.reshape(h, row_pixels, 4)[:, :w, :]
    bgr = cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR)
    return bgr

def main():
    if not ndi.initialize():
        raise RuntimeError("NDI init failed")

    # Discover
    finder = ndi.find_create_v2(ndi.FindCreate())
    time.sleep(2.0)
    sources = ndi.find_get_current_sources(finder) or []
    if not sources:
        raise RuntimeError("No NDI sources discovered")

    src = next((s for s in sources if MATCH.lower() in s.ndi_name.lower()), sources[0])
    print("Connecting to:", src.ndi_name)

    # Receiver with explicit format
    rs = ndi.RecvCreateV3()
    rs.color_format = ndi.RECV_COLOR_FORMAT_BGRX_BGRA
    rs.bandwidth = ndi.RECV_BANDWIDTH_HIGHEST
    rs.allow_video_fields = False
    recv = ndi.recv_create_v3(rs)
    if recv is None:
        raise RuntimeError("recv_create_v3 failed")

    ndi.recv_connect(recv, src)

    # Try for up to ~6s
    end = time.time() + 6.0
    saved = False
    while time.time() < end and not saved:
        state, v, a, m = ndi.recv_capture_v3(recv, 500)
        if state == ndi.FRAME_TYPE_VIDEO:
            try:
                img = video_frame_to_bgr(v)
                cv2.imwrite("received.png", img)
                print("Saved received.png", img.shape[1], "x", img.shape[0])
                saved = True
            finally:
                ndi.recv_free_video_v2(recv, v)
        elif state == ndi.FRAME_TYPE_NONE:
            time.sleep(0.05)
        else:
            # ignore audio / metadata for this test
            pass

    ndi.recv_destroy(recv)
    ndi.find_destroy(finder)
    ndi.destroy()

    if not saved:
        raise RuntimeError("No video frame received (timed out)")

if __name__ == "__main__":
    main()

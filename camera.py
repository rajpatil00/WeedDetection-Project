import cv2
import threading
import time

class Camera:
    def __init__(self, src=0):
        self.video = cv2.VideoCapture(src)

        # ✅ FIX 1: Lowered from 1280x720 → 640x480
        # 1280x720 was too heavy for Pi and caused power crash/restart
        self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        # ✅ FIX 2: Limit to 15 FPS — reduces CPU load significantly
        # Without this the camera ran at max speed and maxed out the CPU
        self.video.set(cv2.CAP_PROP_FPS, 30)

        self._frame_count = 0
        self.latest_frame = None
        self.running = True
        self.lock = threading.Lock()

        # Try to read first frame
        success, image = self.video.read()
        if success:
            self.latest_frame = image

        # Start background capture thread to prevent buffer lag
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()

    def _capture_loop(self):
        while self.running:
            success, image = self.video.read()
            if success:
                with self.lock:
                    self.latest_frame = image.copy()
            else:
                time.sleep(0.01)

    def __del__(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=1.0)
        if hasattr(self, 'video') and self.video.isOpened():
            self.video.release()

    def get_frame(self):
        with self.lock:
            if self.latest_frame is not None:
                self._frame_count += 1
                return self.latest_frame.copy()
            return None

    def should_detect(self, every_n=3):
        return self._frame_count % every_n == 0

    def get_stream_frame(self, frame=None):
        if frame is None:
            frame = self.get_frame()
            if frame is None:
                return None

        # Increased JPEG quality since we have more CPU headroom with background thread
        ret, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        if not ret:
            return None
        return jpeg.tobytes()

from flask import Flask, Response, jsonify, request
from flask_cors import CORS
from motor import MotorController
from arm import ArmController
from camera import Camera
from weed_detector import WeedDetector
from utils import setup_gpio, cleanup_gpio, FLASK_PORT, FLASK_HOST, CAMERA_SOURCE
import time
import logging
import threading

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WeedBotApp:
    def __init__(self):
        self.app = Flask(__name__)
        CORS(self.app, resources={r"/*": {"origins": "*"}})

        # Initialize Hardware
        setup_gpio()
        self.motor = MotorController()
        self.arm = ArmController()
        self.camera = Camera()
        self.detector = WeedDetector()

        self.auto_mode_active = False
        self.detection_enabled = True
        
        # Start background detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        self._setup_routes()

    def _setup_routes(self):
        self.app.add_url_rule('/video_feed', 'video_feed', self.video_feed)
        self.app.add_url_rule('/move', 'move', self.move, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/servo', 'control_servo', self.control_servo, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/mode', 'toggle_mode', self.toggle_mode, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/auto', 'auto_toggle', self.toggle_mode, methods=['POST', 'OPTIONS'])
        self.app.add_url_rule('/status', 'get_status', self.get_status, methods=['GET'])
        self.app.add_url_rule('/heartbeat', 'heartbeat', self.heartbeat, methods=['GET'])
        self.app.add_url_rule('/toggle_detect', 'toggle_detect', self.toggle_detect, methods=['POST', 'OPTIONS'])

    def _detection_loop(self):
        last_annotated = None  # cache last detected frame between skipped frames

        while True:
            try:
                if not self.detection_enabled:
                    if self.auto_mode_active:
                        self.arm.reset_position()
                    time.sleep(0.1)
                    continue

                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                weed_x = None

                if self.detection_enabled:
                    # ✅ FIX: Only run heavy ONNX detection every 3rd frame
                    # Running it every frame was overloading the Pi CPU → crash/restart
                    if self.camera.should_detect(every_n=3):
                        frame, weed_x = self.detector.detect(frame)
                        last_annotated = frame.copy()
                    elif last_annotated is not None:
                        # Reuse last annotated frame to keep bounding boxes visible
                        frame = last_annotated.copy()

                # Arm control only activates in auto mode
                if self.auto_mode_active:
                    if weed_x is not None:
                        self.arm.target_weed(weed_x, frame_width=frame.shape[1])
                    else:
                        self.arm.reset_position()
            except Exception as e:
                logger.error(f"Detection error: {e}")
            
            # Prevent 100% CPU usage if detection is too fast
            time.sleep(0.01)

    def generate_frames(self):
        """Streams the latest frame immediately, drawing stale bounding boxes if needed."""
        while True:
            try:
                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(0.05)
                    continue

                if self.detection_enabled:
                    # Very fast, just draws last known boxes without running ONNX
                    frame = self.detector.annotate_frame(frame)

                stream_frame = self.camera.get_stream_frame(frame)
                if stream_frame:
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + stream_frame + b'\r\n')
                
                # Stream at ~30 FPS for smooth video
                time.sleep(0.033)

            except Exception as e:
                logger.error(f"Frame generation error: {e}")
                time.sleep(0.1)
                continue

    def video_feed(self):
        return Response(self.generate_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')

    def move(self):
        data = request.json or {}
        command = data.get('command') or data.get('direction')
        speed = data.get('speed')

        if self.auto_mode_active:
            logger.warning(f"Rejected Manual Move: {command} (Auto mode is active)")
            return jsonify({'success': False, 'message': 'Manual control disabled while Auto Mode is active'}), 400

        logger.info(f"Move Command: {command}, Speed: {speed}")

        valid_commands = {
            'forward': self.motor.forward,
            'backward': self.motor.backward,
            'left': self.motor.left,
            'rotate_left': self.motor.left,
            'right': self.motor.right,
            'rotate_right': self.motor.right,
            'stop': self.motor.stop
        }

        if command in valid_commands:
            if command == 'stop':
                valid_commands[command]()
            else:
                valid_commands[command](speed)
            return jsonify({'success': True, 'command': command, 'speed': speed})

        return jsonify({'success': False, 'message': f'Invalid command: {command}'}), 400

    def control_servo(self):
        data = request.json or {}
        servo_id = data.get('servo_id')
        angle = data.get('angle')

        if servo_id is not None and angle is not None:
            self.arm.set_servo(int(servo_id), int(angle))
            return jsonify({'success': True, 'servo_id': servo_id, 'angle': angle})
            
        return jsonify({'success': False, 'message': 'Missing servo_id or angle'}), 400

    def toggle_mode(self):
        data = request.json or {}

        if request.path == '/auto' and not data:
            self.auto_mode_active = not self.auto_mode_active
        else:
            mode = data.get('mode', 'auto' if not self.auto_mode_active else 'manual')
            self.auto_mode_active = (mode == 'auto')

        if self.auto_mode_active:
            self.motor.stop()
        else:
            self.arm.reset_position()

        return jsonify({'success': True, 'mode': 'auto' if self.auto_mode_active else 'manual'})

    def toggle_detect(self):
        data = request.json or {}
        if 'enabled' in data:
            self.detection_enabled = bool(data['enabled'])
        else:
            self.detection_enabled = not self.detection_enabled
        return jsonify({'success': True, 'detection_enabled': self.detection_enabled})

    def get_status(self):
        return jsonify({
            'online': True,
            'auto_mode': self.auto_mode_active,
            'detection_enabled': self.detection_enabled,
            'timestamp': time.time()
        })

    def heartbeat(self):
        return jsonify({'status': 'alive', 'timestamp': time.time()})

    def run(self):
        try:
            self.app.run(host=FLASK_HOST, port=FLASK_PORT, threaded=True)
        finally:
            cleanup_gpio()
            self.motor.cleanup()
            self.arm.cleanup()

if __name__ == '__main__':
    bot = WeedBotApp()
    bot.run()

import time
from utils import get_arduino_serial

class ArmController:
    def __init__(self):
        self.arduino = get_arduino_serial()
        self.servos = {1: 0, 2: 0, 3: 0, 4: 0} # Default position

    def set_servo(self, servo_id, angle):
        if angle < 0: angle = 0
        if angle > 180: angle = 180
        
        # Optimization: Only send Bluetooth command if the angle actually changed 
        # to prevent choking the Serial buffer during 30 FPS Auto Mode.
        if self.servos.get(servo_id) == angle:
            return
            
        self.servos[servo_id] = angle
        command = f"S{servo_id}-{angle}\n"
        from utils import safe_write_serial
        safe_write_serial(command.encode())

    def target_weed(self, x_coordinate, frame_width=640):
        # Base (Servo 1): Target the weed's X coordinate
        target_angle = 180 - int((x_coordinate / frame_width) * 180)
        self.set_servo(1, target_angle)
        
        # Shoulder (Servo 2), Elbow (Servo 3), Gripper (Servo 4) "Strike" Position:
        self.set_servo(2, 45)  # Lean forward
        self.set_servo(3, 130) # Extend elbow down
        self.set_servo(4, 30)  # Open/Close gripper slightly

    def reset_position(self):
        # Fold the arm back up to a safe travel position
        self.set_servo(1, 90) # Center base
        self.set_servo(2, 90) # Shoulder straight up
        self.set_servo(3, 90) # Elbow straight
        self.set_servo(4, 0)  # Gripper safe
        
    def cleanup(self):
        pass # Arduino handles pins

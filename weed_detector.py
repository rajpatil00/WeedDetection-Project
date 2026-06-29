import cv2
import numpy as np
import onnxruntime as ort
import os

class WeedDetector:
    def __init__(self, model_path=None):
        self.INPUT_SIZE = 640
        self.CONF_THRESHOLD = 0.30  # Balanced for proper detection
        self.NMS_THRESHOLD = 0.50   # Standard overlap allowance
        
        # ✅ FIXED: Use absolute path so it works regardless of working directory
        if model_path is None:
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weed_detector.onnx")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"ONNX model not found at: {model_path}")

        # Load ONNX model
        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name
        
        # State for separating detection from drawing
        self.last_detections = []
        self.last_max_conf = 0.0
        self.last_target_weed_center_x = None
        self.last_found_count = 0
        self.last_error = None

    def preprocess(self, frame):
        """
        Standard YOLOv8 Preprocessing with Natural Colors and Aspect Ratio Preservation.
        """
        # 1. Letterbox (Pad to 640x640) - No artificial color enhancement to preserve model accuracy
        h, w = frame.shape[:2]
        self.pad_top = (self.INPUT_SIZE - h) // 2
        self.pad_bottom = self.INPUT_SIZE - h - self.pad_top
        self.pad_left = (self.INPUT_SIZE - w) // 2
        self.pad_right = self.INPUT_SIZE - w - self.pad_left
        
        img = cv2.copyMakeBorder(frame, self.pad_top, self.pad_bottom, 
                                 self.pad_left, self.pad_right, 
                                 cv2.BORDER_CONSTANT, value=(0, 0, 0))
        
        # 2. Standard Normalization (RGB, 0-1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32) / 255.0
        img = np.transpose(img, (2,0,1))
        img = np.expand_dims(img, axis=0)
        return img

    def detect(self, frame):
        """
        Detects weeds and updates internal state, then returns the annotated frame.
        """
        if frame is None:
            return frame, None

        self.last_error = None
        try:
            img = self.preprocess(frame)
            outputs = self.session.run(None, {self.input_name: img})
            detections = outputs[0][0].T

            # Auto-detect scale
            is_normalized = False
            if len(detections) > 0:
                max_coord = np.max(detections[:, :2])
                if max_coord < 1.05:
                    is_normalized = True

            boxes = []
            scores = []
            max_conf = 0

            for det in detections:
                x, y, w, h_box, conf = det
                if conf > max_conf: max_conf = conf

                if conf > self.CONF_THRESHOLD:
                    scale = self.INPUT_SIZE if is_normalized else 1.0
                    x_c, y_c = x * scale, y * scale
                    bw, bh = w * scale, h_box * scale
                    x1 = int(x_c - bw/2 - self.pad_left)
                    y1 = int(y_c - bh/2 - self.pad_top)
                    boxes.append([x1, y1, int(bw), int(bh)])
                    scores.append(float(conf))

            self.last_max_conf = max_conf
            self.last_detections = []
            
            target_weed_center_x = None
            max_score = 0
            
            if len(boxes) > 0:
                indices = cv2.dnn.NMSBoxes(boxes, scores, self.CONF_THRESHOLD, self.NMS_THRESHOLD)
                
                if len(indices) > 0:
                    indices_flat = indices.flatten() if hasattr(indices, 'flatten') else indices
                    self.last_found_count = len(indices_flat)
                    
                    for i in indices_flat:
                        idx = int(i)
                        x_box, y_box, w_box, h_box = boxes[idx]
                        conf_val = scores[idx]

                        if conf_val > max_score:
                            max_score = conf_val
                            target_weed_center_x = x_box + (w_box // 2)

                        self.last_detections.append({
                            'box': (x_box, y_box, w_box, h_box),
                            'conf': conf_val
                        })
                else:
                    self.last_found_count = 0
            else:
                self.last_found_count = 0

            self.last_target_weed_center_x = target_weed_center_x

        except Exception as e:
            self.last_error = str(e)[:30]
            return frame, None

        return self.annotate_frame(frame), self.last_target_weed_center_x

    def annotate_frame(self, frame):
        """
        Draws the most recent detections on the given frame.
        """
        if frame is None:
            return frame
            
        h_f, w_f = frame.shape[:2]
        
        cv2.putText(frame, "System: Natural Mode", (10, 25), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

        if self.last_error:
            cv2.putText(frame, f"Error: {self.last_error}", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            return frame

        cv2.putText(frame, f"Peak Conf: {self.last_max_conf:.2f}", (10, 50), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

        for det in self.last_detections:
            x_box, y_box, w_box, h_box = det['box']
            conf_val = det['conf']
            
            # Color-coded detection: Green for High Conf (>0.5), Orange for Medium
            color = (0, 255, 0) if conf_val > 0.50 else (0, 165, 255)
            
            cv2.rectangle(frame, (x_box, y_box), (x_box + w_box, y_box + h_box), color, 3)
            label = f"WEED {conf_val:.2f}"
            cv2.rectangle(frame, (x_box, y_box - 25), (x_box + 120, y_box), color, -1)
            cv2.putText(frame, label, (x_box + 5, y_box - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.circle(frame, (x_box + w_box // 2, y_box + h_box // 2), 7, (0, 0, 255), -1)

        if self.last_found_count > 0:
            cv2.putText(frame, f"Found: {self.last_found_count}", (w_f-120, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "Searching...", (w_f-120, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 1)

        return frame

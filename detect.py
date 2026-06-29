import cv2
import numpy as np
import onnxruntime as ort

# Load ONNX model
session = ort.InferenceSession("best.onnx")
input_name = session.get_inputs()[0].name

cap = cv2.VideoCapture(0)

INPUT_SIZE = 640
CONF_THRESHOLD = 0.6
NMS_THRESHOLD = 0.45

def preprocess(frame):
    img = cv2.resize(frame, (INPUT_SIZE, INPUT_SIZE))
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.astype(np.float32) / 255.0
    img = np.transpose(img, (2,0,1))
    img = np.expand_dims(img, axis=0)
    return img

while True:

    ret, frame = cap.read()
    if not ret:
        break

    img = preprocess(frame)

    outputs = session.run(None, {input_name: img})
    # YOLOv8 output handling
    detections = outputs[0][0].T

    boxes = []
    scores = []

    for det in detections:
        x, y, w, h, conf = det

        if conf > CONF_THRESHOLD:
            # Convert from center-x, center-y, width, height to top-left-x, top-left-y, width, height
            x1 = int((x - w/2) * frame.shape[1] / INPUT_SIZE)
            y1 = int((y - h/2) * frame.shape[0] / INPUT_SIZE)
            bw = int(w * frame.shape[1] / INPUT_SIZE)
            bh = int(h * frame.shape[0] / INPUT_SIZE)

            boxes.append([x1, y1, bw, bh])
            scores.append(float(conf))

    indices = cv2.dnn.NMSBoxes(boxes, scores, CONF_THRESHOLD, NMS_THRESHOLD)

    if len(indices) > 0:
        for i in indices:
            if isinstance(i, (list, np.ndarray)):
                idx = int(i[0])
            else:
                idx = int(i)
                
            x, y, w, h = boxes[idx]

            cv2.rectangle(frame,(x,y),(x+w,y+h),(0,255,0),2)
            label = f"Weed {scores[idx]:.2f}"
            cv2.putText(frame, label, (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    cv2.imshow("Weed Detection", frame)

    if cv2.waitKey(1)==27:
        break

cap.release()
cv2.destroyAllWindows()

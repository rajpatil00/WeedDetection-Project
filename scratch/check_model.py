import onnxruntime as ort
import os

model_path = r"c:\Users\Prathmesh Shah\WeedBot_FlaskApp\weed_detector.onnx"
if not os.path.exists(model_path):
    print(f"Model not found at {model_path}")
else:
    session = ort.InferenceSession(model_path)
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    
    print("Inputs:")
    for i in inputs:
        print(f"  {i.name}: {i.shape}, {i.type}")
        
    print("Outputs:")
    for o in outputs:
        print(f"  {o.name}: {o.shape}, {o.type}")

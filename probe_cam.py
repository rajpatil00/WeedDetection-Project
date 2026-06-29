import cv2

def probe_cameras():
    print("Probing camera indices 0-5...")
    for i in range(10):
        print(f"Probing Index {i}...")
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap.isOpened():
            ret, _ = cap.read()
            if ret:
                print(f"Index {i}: WORKING (DSHOW)")
            else:
                print(f"Index {i}: OPENED BUT NO FRAME (DSHOW)")
            cap.release()
        else:
            print(f"Index {i}: ERR (DSHOW)")

if __name__ == "__main__":
    probe_cameras()

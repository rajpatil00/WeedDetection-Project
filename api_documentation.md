# WeedBot AI - API Documentation

This document describes all available endpoints for controlling the WeedBot robot. This is designed to be compatible with your mobile application.

## Base URL
`http://<RASPBERRY_PI_IP>:5000`

> [!NOTE]
> The backend now uses a Serial bridge to offload motor and arm control to an Arduino Mega 2560. Ensure the Arduino is connected via USB and running the `ArduinoControl.ino` sketch.

---

## 1. Robot Movement
**Endpoint**: `/move`  
**Method**: `POST`  
**Description**: Controls the robot's wheels.

**JSON Body**:
```json
{
  "direction": "forward", 
  "speed": 80
}
```
*Note: You can also use "command" instead of "direction".*

**Valid Directions**: `forward`, `backward`, `left`, `right`, `rotate_left`, `rotate_right`, `stop`.  
**Speed**: Number between 0 and 100.

---

## 2. Robotic Arm Control
**Endpoint**: `/arm`  
**Method**: `POST`  
**Description**: Manual control of the robotic weeding arm.

**JSON Body**:
```json
{
  "direction": "left"
}
```
**Valid Directions**: `left`, `right`, `center`.

---

## 3. Auto Mode Toggle
**Endpoint**: `/auto` (or `/mode`)  
**Method**: `POST`  
**Description**: Toggles autonomous weed detection.

**JSON Body** (Optional):
```json
{
  "mode": "auto"
}
```
*If no JSON body is provided, the mode will simply toggle.*

---

## 4. Video Stream
**Endpoint**: `/video_feed`  
**Method**: `GET`  
**Description**: Access the live 720p HD MJPEG stream.

---

## 5. System Status
**Endpoint**: `/status`  
**Method**: `GET`  
**Description**: Returns current robot state.

**Response**:
```json
{
  "online": true,
  "auto_mode": false,
  "timestamp": 123456789.0
}
```

---

## 6. Heartbeat (Latency Check)
**Endpoint**: `/heartbeat`  
**Method**: `GET`  
**Description**: Simple lightweight check to verify connection and measure latency.

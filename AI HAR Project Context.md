# **Context: AI Human Activity Recognition for On-board BAS Experiments (Problem Statement 26174\)**

## **1\. Core Problem Statement**

> * **Goal:** Build an AI-based Human Activity Recognition (HAR) system to act as an on-board assistant for astronauts executing scientific experiments in space (microgravity).  
> * **Key Constraints:**  
  * Must operate entirely offline (standalone edge compute).  
  * No fixed "up" or "down" (orientation-agnostic tracking relative to the payload rack).  
  * Fixed-payload cameras.  
> * **Required Deliverables:**  
  * Continuously track experiment sequences.  
  * Provide next-step suggestions.  
  * Generate voice-based alerts for skipped or out-of-order steps.  
  * Output a timestamped, structured lightweight text file of steps and status.  
  * Save video locally AND stream to a specific target IP.  
  * Provide a monitoring GUI.

## **2\. Target Demonstration Hardware**

> * **Machine:** Lenovo Legion Laptop  
> * **GPU:** NVIDIA RTX 4060 (8GB VRAM) with NVENC encoding.  
> * **Performance:** Sufficient to run the entire pipeline (vision, logic, TTS, web server, and video streaming) locally for hackathon/jury demonstrations using quantized or lightweight models.

## **3\. Simplified Local Tech Stack**

> * **Computer Vision Pipeline:**  
  * *Object/Tool Detection:* Ultralytics YOLOv11 Nano/Small (Exported to TensorRT for max FPS).  
  * *Body/Hand Tracking:* MediaPipe Holistic (Runs on CPU/optimized, provides 3D hand keypoints).  
  * *Interaction Logic:* Spatial heuristics (e.g., checking if hand keypoints intersect with tool bounding boxes) rather than heavy 3D mesh rendering.  
> * **Logic & Sequence Validation:**  
  * *State Machine:* Python transitions library to model the experiment as a Deterministic Finite Automaton (FSM).  
> * **Audio Alerts & Logging:**  
  * *Voice:* pyttsx3 or Piper for offline, zero-latency text-to-speech.  
  * *Telemetry:* Python json and logging modules for the structured output file.  
> * **Video & GUI:**  
  * *Streaming:* OpenCV \+ FastAPI (or MediaMTX) serving MJPEG or RTSP streams over local Wi-Fi.  
  * *Storage:* OpenCV cv2.VideoWriter appending to local .mp4.  
  * *GUI:* Streamlit or simple React/FastAPI dashboard for live monitoring and checklist tracking.

## **4\. Relevant Open-Source References to Study**

> * **Procedural Logic / Mistake Detection:**  
  * *PREGO (Online Mistake Detection):* Great reference for comparing expected vs. actual actions using symbolic reasoning.  
  * *Assembly101:* Excellent dataset/benchmark for procedural task tracking and mistake detection.  
> * **Hand-Object Interaction (HOI):**  
  * *100DOH (Hand-Object Detector):* Tracks hands, objects, and contact states (grasping vs. empty).  
  * *Ego-Exo4D (Meta AI):* Foundational repo for tracking skilled lab tasks and generating text logs.  
> * **Action Frameworks:**  
  * *MMAction2:* OpenMMLab’s toolbox for temporal action segmentation.
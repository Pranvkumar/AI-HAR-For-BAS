Hello Claude. I am providing you with a context document titled "AI HAR Project Context" that outlines a project I am building: an AI Human Activity Recognition system for astronaut scientific experiments (Problem Statement 26174).  
Please read the context document carefully, keeping in mind that this will be demonstrated locally on a Lenovo Legion laptop (RTX 4060, 8GB VRAM) before eventually being targeted for space-grade edge hardware.  
Based on this context, please complete the following three tasks:

> 1. DETAILED SYSTEM ARCHITECTURE  
>    Create a detailed, module-by-module system architecture based on the "Simplified Local Tech Stack" provided in the context. Explain exactly how data flows from the camera frame ingestion, through the YOLO/MediaPipe vision models, into the Python State Machine (FSM), and finally out to the UI, local video storage, IP stream, and TTS audio alerts.  
> 2. ARCHITECTURE IMPROVEMENTS  
>    Analyze the proposed stack and suggest specific improvements. Focus on:  
> * Handling edge cases in a microgravity simulation (e.g., occlusions, floating objects).  
> * Fault tolerance in the FSM (how to recover if the AI misses a step but the user continues).  
> * Efficient VRAM management on the 8GB RTX 4060 while running YOLO, TTS, and video encoding simultaneously.  
> 3. EXECUTION PLAN FOR MID-RANGE/LOCAL MODELS  
>    Create a step-by-step development roadmap. Because of the hardware constraints, this plan MUST exclusively utilize mid-range, lightweight, or highly optimized local models (like YOLO Nano/Small, MediaPipe CPU tasks, and lightweight offline TTS). Provide a phased plan covering:  
> * Phase 1: Data Collection & Model Training (Focusing on the specific tools).  
> * Phase 2: Vision & FSM Integration (How to map hand-object interactions to state changes).  
> * Phase 3: Telemetry, Video Streaming, & UI.  
> * Phase 4: Optimization (TensorRT integration).

Please be highly technical, specific, and format your response clearly.
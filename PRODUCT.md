# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
React 18, TypeScript, Vite, TailwindCSS, FastAPI, Python 3.10+, SQLite, WebSockets.

## Users
- Primary: Payload Specialists and Astronauts executing scientific protocols inside space station rack bays (Bharatiya Antariksh Station / ISS).
- Secondary: Flight Directors and Ground Control (POIC) monitoring telemetry and procedural conformance via deep-space downlink.

## Product Purpose
AEGIS is an enterprise-grade avionics operations console and onboard AI assistant for scientific payload validation in microgravity environments. It continuously validates procedural compliance against DO-178C finite state machines, detects critical safety hazards in microgravity, and provides zero-latency autonomous feedback.

## Positioning
Real-time onboard computer vision and physics-based microgravity hazard prevention (slosh jerk, FOD drift, immobility) combined with a DO-178C cryptographic Merkle Flight Ledger and CCSDS 133.0-B-2 space telemetry framing that no general-purpose computer vision tool provides.

## Operating Context
- Onboard microgravity environment (low ambient noise, glove/suit interaction, variable lighting, zero-g free-floating objects).
- High-reliability flight operations where cognitive distraction or procedure sequencing error risks mission safety.
- Low-bandwidth deep-space downlinks requiring extreme data compression (3D Digital Twin at ~0.5 KB/s vs 2.5 MB/s raw video).

## Capabilities and Constraints
- sub-25ms optical action classification.
- DO-178C Finite State Machine validation with strict violation interrupts.
- DO-178C Cryptographic Merkle Flight Ledger with SHA-256 block chain verification.
- Autonomous Copilot guidance grounded in live state.
- Physical safety governors: Slosh guard, immobility detection, optical glare detection, FOD drift tracking, biometric verification, thermal and USB hardware watchdogs.
- Constraint: Low CPU overhead on fanless embedded hardware (SWaP-C eco-governor).

## Brand Commitments
- Name: AEGIS AI-HAR Avionics Operations Console.
- Visual World: Obsidian Spacecraft Flight Operations (NASA Ames/JPL Open MCT & SpaceX Dragon telemetry aesthetics).
- Palette: Obsidian base (`#07090e`), electric cyan (`#0ea5e9`), precision emerald (`#10b981`), warning amber (`#f59e0b`), tactical crimson (`#f43f5e`), cryptographic violet (`#818cf8`).

## Evidence on Hand
- Live telemetry feeds from onboard webcams and USB cameras (`/api/v1/monitoring/stream`).
- Simulated procedural workflows (`nominal`, `low_confidence`, `violation`).
- Real-time WebSocket feed (`/ws/monitoring`).
- SQLite session database (`storage/aegis.db`).

## Product Principles
1. Safety First: Any critical safety violation (slosh, immobility, glare) immediately overrides routine UI displays.
2. Zero Cognitive Clutter: Dense information architecture with strict visual hierarchy and tabular alignment; no decorative distractions.
3. Transparent Auditability: Every state transition is cryptographically chained and verifiable down to the block hash.
4. Autonomous Resilience: Graceful degradation between live physical camera, browser webcam, and synthetic simulation.

## Accessibility & Inclusion
- High-contrast visual ratio (≥4.5:1 for body copy).
- Tabular numerals (`font-mono`) across all data displays.
- Visual and auditory multimodal indicators for all alarm states.

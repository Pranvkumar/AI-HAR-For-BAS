---
name: frontend-design
description: Guidance for distinctive, intentional visual design when building new UI or reshaping an existing one. Helps with aesthetic direction, typography, and making choices that don't read as templated defaults.
---

# Frontend Design

Approach this as the design lead at a top design studio known for giving every product a distinct, unforgettable visual identity. The user requires a modern, premium, state-of-the-art UI/UX that feels truly custom, fluid, and visually stunning.

## Design Principles

### Ground Your Designs in the Subject Matter
- For mission-critical space station operations, use sleek aerospace HUD styling, crisp monospace telemetry accents, glowing indicators, high-contrast dark space themes, glassmorphism panels with ultra-subtle borders, and vibrant aerospace cyan/emerald/amber/violet accents.
- Every element should feel purpose-built, responsive, and tactile.

### Typography & Hierarchy
- Use modern, high-grade fonts: Outfit/Inter for clean UI reading and JetBrains Mono/Space Grotesk for telemetry and status metrics.
- Maintain strict line-height hierarchy and tabular numbers (`font-variant-numeric: tabular-nums`) for jitter-free real-time telemetry counters.
- Never use generic low-contrast gray text on dark backgrounds; ensure WCAG 2.1 AA compliant contrast ratios.

### Color & Depth
- Tailored dark space theme (`#080c14`, `#0d1424`, `#131f38`) paired with neon teal (`#00f0ff` / `#14b8a6`), electric amber (`#f59e0b`), pulse red (`#ef4444`), and mission violet (`#8b5cf6`).
- Multi-layered glassmorphic depth (`backdrop-blur-xl`, `bg-space-900/70`, `border border-white/10`, inner glow highlights `box-shadow: inset 0 1px 0 0 rgba(255,255,255,0.05)`).
- Radiant radial gradients that give subtle ambient cockpit lighting to panels and headers.

### Motion & Micro-interactions
- Smooth transitions for hover, focus, and state changes (150ms-250ms cubic-bezier).
- Subtle pulsating beacons for live sensors and active streams.
- Tactile button press feedback (`active:scale-[0.98]`).
- Crisp modal entrances with springy scale-in transitions.

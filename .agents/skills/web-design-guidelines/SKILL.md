---
name: web-design-guidelines
description: Review and craft UI code for compliance with modern Web Interface Guidelines, accessibility (WCAG 2.1 AA), focus states, smooth typography, and high-performance micro-interactions.
---

# Web Interface Guidelines & Modern Design Rules

## 1. Accessibility (A11y)
- Icon-only buttons must have `aria-label` or `title`.
- Interactive elements must be keyboard-operable with clear `:focus-visible` rings.
- Ensure semantic HTML (`<button>`, `<nav>`, `<aside>`, `<header>`, `<main>`, `<section>`).
- Maintain WCAG 2.1 AA contrast ratios across all text and icons.

## 2. Visual Hierarchy & Glassmorphism
- Use subtle backdrop blurs (`backdrop-blur-xl`), semi-transparent dark space surfaces, and fine hairline borders (`border border-white/[0.08]`).
- Add inner specular reflections (`shadow-[inset_0_1px_0_0_rgba(255,255,255,0.06)]`) to give depth to cards and controls.
- Use glowing pill badges with color-matched background tints and glowing borders.

## 3. Typography & Spacing
- Use tabular numbers (`tabular-nums`) for dynamic metrics, coordinates, confidence bars, and timestamps.
- Use `text-wrap: balance` on headers and section titles to prevent lonely words.
- Maintain consistent padding scales (`p-3`, `p-4`, `p-6`) and rounded corners (`rounded-xl`, `rounded-2xl`).

## 4. Tactile Micro-Interactions
- Use smooth CSS transitions: `transition-all duration-200 ease-out`.
- Provide hover lifts and subtle glow expansions on cards (`hover:border-accent-400/40 hover:shadow-lg hover:shadow-accent-500/10`).
- Responsive active button depression (`active:scale-95` or `active:scale-[0.98]`).

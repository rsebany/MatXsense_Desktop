# MatXSense – Visual Identity

Single source of truth for colors, typography, and design tokens used across the project (frontend, charts, presentations, docs).

---

## Brand colors

| Role | Name | Hex | RGB | Usage |
|------|------|-----|-----|--------|
| **Primary** | Deep Navy | `#0B1C2D` | rgb(11, 28, 45) | Page background, main surfaces |
| **Secondary** | Steel Blue | `#1F4FD8` | rgb(31, 79, 216) | Primary buttons, gradients, key UI |
| **Accent** | Teal | `#17C3B2` | rgb(23, 195, 178) | Logo, links, highlights, CTAs |
| **Green** | Success | `#2ECC71` | rgb(46, 204, 113) | Good status, positive metrics |
| **Amber** | Warning | `#F39C12` | rgb(243, 156, 18) | Warnings, alerts, caution |
| **Red** | Danger / Error | `#E74C3C` | rgb(231, 76, 60) | Errors, critical, offline |
| **Gray** | Neutral | `#7F8C8D` | rgb(127, 140, 141) | Disabled, muted actions, info |

---

## UI surface & text

| Token | Hex | Usage |
|-------|-----|--------|
| **Card background** | `#122536` | Cards, panels, modals |
| **Border** | `#1e3a52` | Borders, dividers, grids |
| **Text** | `#e8eef4` | Primary body and headings |
| **Text muted** | `#94a3b8` | Secondary text, labels, hints |

---

## Supporting colors (gradients & hovers)

| Purpose | Hex | Usage |
|---------|-----|--------|
| Secondary button hover | `#2563eb` | Blue in gradient with `#1F4FD8` |
| Accent gradient end | `#14a89a` | Teal gradient with `#17C3B2` (footer CTA) |
| Gray hover | `#95a5a6` | Logout / secondary button hover |

---

## Typography

| Role | Font stack | Weights | Usage |
|------|------------|---------|--------|
| **UI** | `'Inter', 'Segoe UI', sans-serif` | 400, 500, 600, 700 | Buttons, labels, headings, body |
| **Mono** | `'JetBrains Mono', 'IBM Plex Mono', monospace` | 400, 500, 600 | Numbers, codes, API values, RUL |

- **Source:** Google Fonts – Inter + JetBrains Mono  
- **Icons:** Font Awesome 6.4.0 (`fas fa-*`)

---

## Spacing & shape

| Token | Value | Usage |
|-------|--------|--------|
| **Radius** | `12px` | Cards, inputs, buttons, modals |
| **Shadow** | `0 4px 12px rgba(0,0,0,0.15)` | Cards, dropdowns |
| **Container max-width** | `1400px` | Main content wrapper |

---

## Chart.js (dashboard)

Use these in Chart.js configs so charts match the app:

- **Background (tooltip/legend):** `#122536`
- **Border:** `#1e3a52`
- **Title / emphasis text:** `#e8eef4`
- **Body / axis labels:** `#cbd5e1` or `#94a3b8`
- **Grid:** `#1e3a52`
- **Ticks:** `#94a3b8`
- **Dataset – Steel Blue:** `#1F4FD8`, fill `rgba(31, 79, 216, 0.1)`
- **Dataset – Teal:** `#17C3B2`, fill `rgba(23, 195, 178, 0.05)`

---

## Status & alerts

| State | Background (with alpha) | Text/Border |
|-------|-------------------------|-------------|
| Good | `rgba(46, 204, 113, 0.2)` | `#2ECC71` |
| Warning | `rgba(243, 156, 18, 0.2)` / `0.3` | `#F39C12` |
| Danger | `rgba(231, 76, 60, 0.2)` / `0.3` | `#E74C3C` |
| Info / neutral | `rgba(127, 140, 141, 0.3)` | `#7F8C8D` |
| Accent highlight | `rgba(23, 195, 178, 0.15)` / `0.08` | `#17C3B2` |

---

## Logo & icon

- **Logo mark:** Font Awesome `fa-atom` (teal `#17C3B2`, 32px in header).
- **Product name:** “MatXSense” – use **Inter** (or brand font), primary text color `#e8eef4`.
- **Tagline:** “Material Degradation Monitoring” / “AI-powered material health monitoring” – use muted text `#94a3b8`.

---

## CSS variables (frontend)

Use these in `frontend/style.css` so one place controls the identity:

```css
:root {
  --primary: #0B1C2D;
  --secondary: #1F4FD8;
  --accent: #17C3B2;
  --green: #2ECC71;
  --amber: #F39C12;
  --red: #E74C3C;
  --gray: #7F8C8D;
  --bg-card: #122536;
  --border: #1e3a52;
  --text: #e8eef4;
  --text-muted: #94a3b8;
  --font-ui: 'Inter', 'Segoe UI', sans-serif;
  --font-mono: 'JetBrains Mono', 'IBM Plex Mono', monospace;
  --radius: 12px;
  --shadow: 0 4px 12px rgba(0,0,0,0.15);
}
```

---

## Quick reference palette

```
Primary:   #0B1C2D  Deep Navy
Secondary: #1F4FD8  Steel Blue
Accent:    #17C3B2  Teal
Success:   #2ECC71  Green
Warning:   #F39C12  Amber
Error:     #E74C3C  Red
Neutral:   #7F8C8D  Gray
Card:      #122536
Border:    #1e3a52
Text:      #e8eef4
Muted:     #94a3b8
```

Use this doc for UI, slides, and any new screens or components so MatXSense stays visually consistent.

# Portfolio Toolchain UI Mockups v2

This package contains three public-safe UI mockups based on the portfolio's selected toolchain projects:

1. **XCP-Based AI Validation Interface**
2. **Time-Series AI Training Platform**
3. **TOS/ODP BEV Simulator**

## What changed vs the first toy version

The first version was intentionally simple. This v2 version focuses on UI realism:

- portfolio-style hero pages and cards
- dark engineering-console app frames
- session/sidebar panels
- signal tables and synthetic charts
- event logs and status badges
- scenario replay controls
- BEV visualization canvas
- export/workflow panels

## Public-safe constraints

These demos do **not** include:

- company source code
- company screenshots
- company measurement data
- real ECU, transport, or memory-map configuration
- network database identifiers, signal names, internal memory details, calibration metadata, calibration values
- production parameters or internal target-selection logic

The demos use synthetic data and simplified public logic only.

## How to run

Open `index.html` in a browser, then open each demo.

No server is required. No external dependencies are required.

## Recommended portfolio placement

Use these as visual companion pages or embedded screenshots under the portfolio Toolchain section. Add a caption such as:

> Public-safe UI mockup recreated with synthetic data. Original internal tool used production workflows, but company data, signal names, ECU configuration, calibration values, and implementation details are omitted.


v5 update: BEV simulator now visualizes ego RoadRadius = Vx/yawrate vs actual variable-curvature road, with adjacent-lane tracks causing far-field false-detection candidates.


v6 update: BEV simulator vehicle/track rectangles now align to the actual road tangent direction, with a small heading marker for readability.

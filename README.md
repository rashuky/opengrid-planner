# gridPlanner

A simple visual planning tool for laying out **Underware** cable management channels on an **openGrid** desk mounting system.

## Background

[openGrid](https://www.opengrid.world/) is an open-source, modular wall and desk mounting framework built around a **28 mm grid unit**. It is Gridfinity-compatible and integrates natively with [Underware 2.0](https://makerworld.com/pl/models/783010-underware-2-0-infinite-cable-management) — a parametric, snap-in cable management channel system. Before printing and mounting channels under your desk, this tool lets you sketch out the grid layout on screen so you can see how the channels will fit together.

## Setup

```bash
# 1. Create and activate the virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

## Running

```bash
source .venv/bin/activate   # if not already active
python grid_planner.py
```

## Usage

- The canvas represents an openGrid surface divided into cells.
- Each small cell = 1 openGrid unit (28 mm in real life).
- A heavier-bordered block = 10 × 10 cells (one large grid section).
- **Click** anywhere on the canvas to stamp a 10 × 10 block outline at the nearest grid snap point — use this to mark where a grid tile or cable channel run will be placed.

## Dependencies

| Package  | Version |
|----------|---------|
| PySide6  | 6.11.0  |

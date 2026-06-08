# Synthetic Market Simulator

An event-driven synthetic financial market where autonomous trading agents interact with a simulated exchange engine, producing market dynamics for quantitative research, analytics, and visualization.

This repo is currently in the architecture-first phase. No trading engine code has been implemented yet.

## Core Idea

Market events flow through a deterministic exchange engine:

```text
Market Event -> Order Generated -> Order Book -> Matching Engine -> Trade -> Portfolio Update -> Analytics
```

## Architecture Docs

- `docs/architecture/ARCHITECTURE.md` defines the system modules, event flow, data flow, class boundaries, and implementation phases.

## Planned Stack

- Python for simulation, orchestration, analytics, visualization, and research.
- `asyncio` for the initial event engine.
- `dataclasses` for clean domain models.
- `numpy` and `pandas` for simulation and analysis.
- `matplotlib` or `plotly` for visualization.
- Optional C++ later for the matching engine or order book if profiling proves it is needed.

# Abyssal Mining Optimizer & 3D Map

This project provides a web-based 3D visualization and optimization tool for deep-sea mining exploration. It processes geospatial data to identify optimal mining locations based on resource value, extraction difficulty, and environmental impact, while highlighting endangered species to ensure conservation.

## Features

*   **3D Interactive Map:** Visualizes the 50x50km abyssal grid using **Deck.gl** and **MapLibre**, rendering seafloor depth as 3D terrain.
*   **Mining Optimization:** Calculates a "Mining Score" for every cell, weighing economic potential against hazards and environmental costs.
*   **Visualization Modes:**
    *   **Biome View:** Color-coded view of different seafloor biomes (Seamount, Plain, Trench, etc.).
    *   **Mining Score:** Heatmap highlighting high-value mining zones (Yellow/Green) vs. poor locations (Blue/Dark).
*   **Environmental Protection:** Integrates **IUCN Red List** statuses to flag endangered species (e.g., *Specter Whale [CR]*, *Abyssal Ray [EN]*) in potential mining sectors.

## Dataset

The application is powered by **`merged.csv`**, a consolidated dataset containing geospatial and sensor data for 2,500 grid cells. This data includes:
*   **Coordinates:** Latitude, Longitude, Depth.
*   **Environment:** Biome type, Pressure, Temperature.
*   **Resources:** Types (e.g., Manganese Nodules), abundance, and economic value.
*   **Hazards:** Geological threats (e.g., Hydrothermal Vents).
*   **Life Forms:** Species presence and density.

## Technology Stack

*   **Backend:** Python **FastAPI**
*   **Frontend:** HTML5, **Deck.gl** (3D Visualization), **MapLibre GL JS**
*   **Data Processing:** Python (Standard Library)

## Installation & Setup

### 1. Prerequisites
Ensure you have Python 3.8+ installed.

### 2. Install Dependencies
Install the required Python packages:

```bash
pip install fastapi uvicorn
```

*(Note: The application uses standard libraries like `csv`, `json`, and `math` for data processing, so no heavy data science libraries like Pandas are required.)*

### 3. Run the Application
Start the local server using `uvicorn`:

```bash
uvicorn app.main:app --reload
```

### 4. Access the Map
Open your web browser and navigate to:

**http://127.0.0.1:8000**

## Usage

*   **Rotate/Pan:** Left-click + drag to rotate. Right-click + drag to pan. Scroll to zoom.
*   **Toggle Views:** Use the sidebar buttons to switch between "Biome View" and "Mining Score".
*   **Inspect Cells:** Hover over any cell to see live data. Click a cell to lock the sidebar details.
*   **Search:** Enter Row/Col coordinates in the sidebar to locate specific grid cells.


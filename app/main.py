from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import csv
import json
import os
import ast

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

def safe_eval(val):
    """Safely evaluates a string representation of a list."""
    if not val:
        return []
    try:
        if val.startswith('[') and val.endswith(']'):
            return ast.literal_eval(val)
        return val
    except (ValueError, SyntaxError):
        return []

@app.get("/")
async def read_index():
    return FileResponse('app/static/index.html')

@app.get("/api/grid")
async def get_grid():
    data = []
    filepath = 'merged.csv'
    
    if not os.path.exists(filepath):
        return {"error": "merged.csv not found"}
        
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Parse lists for frontend display
            hazards = safe_eval(row.get('hazard_type', '[]'))
            resources = safe_eval(row.get('resource_type', '[]'))
            life = safe_eval(row.get('life_species', '[]'))
            
            # Simplify data for map grid
            cell_data = {
                'row': int(row['row']),
                'col': int(row['col']),
                'lat': float(row['lat']),
                'lon': float(row['lon']),
                'depth': float(row['depth_m']),
                'biome': row['biome'],
                'hazards': hazards,
                'resources': resources,
                'life': life,
                'pressure': float(row['pressure_atm']),
                'temp': float(row['temperature_c'])
            }
            data.append(cell_data)
            
    return data


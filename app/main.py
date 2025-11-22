from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import csv
import json
import os
import ast
import sys
from typing import AsyncGenerator

# Add project root to python path so we can import 'app' module when running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.optimizer import AbyssalOptimizer

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Import our tools
from app.tools import TOOLS

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("GOOGLE_API_KEY not found in environment variables!")

def initialize_agent():
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-preview-09-2025",
        google_api_key=GOOGLE_API_KEY,
        thinking_budget=-1,
    )

    checkpointer = MemorySaver()
    
    system_prompt = """You are an expert deep-sea data analyst assistant for the Abyssal World dataset. 

You have access to a comprehensive merged dataset with the following columns:

COLUMN DATA TYPES:
- LIST columns (contain Python lists): hazard_type, hazard_severity, hazard_notes, life_species, life_avg_depth_m, life_density, life_threat_level, life_behavior, life_trophic_level, life_prey_species, poi_id, poi_category, poi_label, poi_description, poi_research_value, resource_type, resource_family, resource_abundance, resource_purity, resource_extraction_difficulty, resource_environmental_impact, resource_economic_value, resource_description, biome_predators, biome_prey, biome_interaction_strengths
- NUMERIC columns (floats/ints): row, col, x_km, y_km, lat, lon, depth_m, pressure_atm, temperature_c, light_intensity, terrain_roughness, coral_coral_cover_pct, coral_health_index, coral_bleaching_risk, coral_biodiversity_index, current_u_mps, current_v_mps, current_speed_mps
- STRING columns: biome, current_stability (values: "low", "medium", "high")

DETAILED COLUMN DESCRIPTIONS:
- row, col: Grid coordinates (0-49)
- x_km, y_km: Position in kilometers
- lat, lon: Geographic coordinates
- depth_m: Depth in meters
- pressure_atm: Pressure in atmospheres
- biome: Biome type (seamount, trench, plain, slope, hydrothermal)
- temperature_c: Temperature in Celsius
- light_intensity: Light intensity level
- terrain_roughness: Terrain roughness metric

Coral Data:
- coral_coral_cover_pct: Coral coverage percentage
- coral_health_index: Coral health index
- coral_bleaching_risk: Coral bleaching risk level
- coral_biodiversity_index: Coral biodiversity index

Current Data:
- current_u_mps, current_v_mps: Current velocity components (m/s)
- current_speed_mps: Current speed (m/s)
- current_stability: Current stability metric
- current_flow_direction: Flow direction

Hazard Data:
- hazard_type: List of hazard types
- hazard_severity: List of hazard severities (low, medium, high, extreme)
- hazard_notes: List of hazard descriptions

Life/Species Data:
- life_species: List of species names
- life_avg_depth_m: List of average depths for each species
- life_density: List of species densities
- life_threat_level: List of threat levels (1-5)
- life_behavior: List of behaviors (solitary, swarm, territorial, etc.)
- life_trophic_level: List of trophic levels (1-5)
- life_prey_species: List of prey species (semicolon-separated)

Points of Interest:
- poi_id: List of POI IDs
- poi_category: List of POI categories
- poi_label: List of POI labels
- poi_description: List of POI descriptions
- poi_research_value: List of research values

Resource Data:
- resource_type: List of resource types
- resource_family: List of resource families
- resource_abundance: List of abundance values
- resource_purity: List of purity percentages
- resource_extraction_difficulty: List of extraction difficulty scores
- resource_environmental_impact: List of environmental impact scores
- resource_economic_value: List of economic values (THIS IS IMPORTANT FOR QUERIES)
- resource_description: List of resource descriptions

Food Web Data:
- biome_predators: List of predator species in the biome
- biome_prey: List of prey species in the biome
- biome_interaction_strengths: List of interaction strengths

TOOLS AVAILABLE:
1. query_data(code): Execute Python/Pandas code to analyze data and return information (strings, numbers, statistics).
   - Assign result to variable 'result'
   - Use for: counts, statistics, max/min values, general information
   - Does NOT highlight tiles

2. query_and_highlight(code): Execute Python/Pandas code to find tiles AND automatically highlight them.
   - Assign result to variable 'result_rows' as list of {'row': X, 'col': Y} dicts
   - Use for: "find top 5 richest tiles", "show all deep tiles", etc.
   - Automatically highlights the results

3. highlight_tiles(tiles): Manually highlight specific tiles on the map.
   - Pass a list of dicts with 'row' and 'col' keys
   - Use when you already have specific coordinates to highlight

IMPORTANT NOTES:
- List columns (like resource_economic_value, life_species, etc.) contain Python lists when multiple items exist for a cell
- Use pandas operations to filter, sort, and analyze the data
- When user asks to "find" or "show" tiles, use query_and_highlight (it auto-highlights)
- When user asks "how many" or wants statistics, use query_data (no highlighting)
- Economic value is stored in resource_economic_value as a list of values
- IF you are asked to search for something, and you are returned a empty result, then YOU MUST make a query_data  tool call to get all the unique values for a column to find the correct key. CAUTION: Do not do this for the columns that do not contain string or list values. After this, return your response to the user."""

    agent = create_agent(
        model=model,
        tools=TOOLS,
        checkpointer=checkpointer,
        system_prompt=system_prompt,
    )
    
    return agent

agent = initialize_agent() if GOOGLE_API_KEY else None
thread_id = 0

class ChatRequest(BaseModel):
    message: str

# --- ENDPOINTS ---

def safe_eval(val):
    if not val:
        return []
    try:
        val = val.strip()
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
    optimizer = AbyssalOptimizer()
    
    # Load data
    if not optimizer.load_data():
        return {"error": "merged.csv not found"}
        
    # Calculate scores with default weights
    weights = {
        'value': 1.0,
        'difficulty': 1.0,
        'impact': 2.0,
        'hazard': 2.0
    }
    
    scored_data = optimizer.calculate_scores(weights)
    
    # Now load full CSV data to add full_data field
    filepath = 'merged.csv'
    full_data_map = {}  # Map (row, col) -> full_data dict
    
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                full_data = {}
                for k, v in row.items():
                    if v and v.strip():
                        if v.strip().startswith('[') and v.strip().endswith(']'):
                            full_data[k] = safe_eval(v)
                        else:
                            try:
                                if '.' in v:
                                    full_data[k] = float(v)
                                else:
                                    full_data[k] = int(v)
                            except ValueError:
                                full_data[k] = v
                
                key = (int(row['row']), int(row['col']))
                full_data_map[key] = full_data
    
    # Merge full_data into scored_data
    for item in scored_data:
        key = (item['row'], item['col'])
        item['full_data'] = full_data_map.get(key, {})
    
    return scored_data

async def generate_response(user_message: str) -> AsyncGenerator[str, None]:
    global agent, thread_id
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        async for token, metadata in agent.astream(
            {"messages": [HumanMessage(content=user_message)]},
            config=config,
            stream_mode="messages"
        ):
            if not token.content_blocks:
                continue
            
            for message in token.content_blocks:
                msg_type = message.get("type")
                node = metadata.get("langgraph_node")
            
                if msg_type == "text" and node == "model":
                    yield json.dumps({"type": "text", "content": message["text"]}) + "\n"
                    
                elif msg_type == "text" and node == "tools":
                    # Tool outputs come as text messages from the tools node
                    content = message.get("text", "")
                    print(f"[DEBUG] Tool output: {content[:150]}")
                    
                    # Check if this is a query_and_highlight result with HIGHLIGHT: prefix
                    if isinstance(content, str) and content.startswith("HIGHLIGHT:"):
                        try:
                            tiles_str = content[10:]  # Remove "HIGHLIGHT:" prefix
                            tiles = ast.literal_eval(tiles_str)
                            
                            if isinstance(tiles, list) and len(tiles) > 0:
                                yield json.dumps({"type": "highlight", "tiles": tiles}) + "\n"

                        except Exception as e:
                            yield json.dumps({"type": "text", "content": f"⚠ Highlight error: {str(e)}"}) + "\n"
                
                       
    except Exception as e:
        yield json.dumps({"type": "text", "content": f"Error: {str(e)}"}) + "\n"

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not agent:
        async def error_gen():
            yield json.dumps({"type": "text", "content": "API Key missing"}) + "\n"
        return StreamingResponse(error_gen(), media_type="application/x-ndjson")
    
    return StreamingResponse(
        generate_response(request.message),
        media_type="application/x-ndjson"
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


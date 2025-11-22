import pandas as pd
import ast
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# Load data once for the tools
DF = pd.read_csv('merged.csv')

# Parse list columns from strings to actual lists
# These columns contain stringified lists like "[item1, item2]"
list_columns = [
    'hazard_type', 'hazard_severity', 'hazard_notes',
    'life_species', 'life_avg_depth_m', 'life_density', 'life_threat_level', 
    'life_behavior', 'life_trophic_level', 'life_prey_species',
    'poi_id', 'poi_category', 'poi_label', 'poi_description', 'poi_research_value',
    'resource_type', 'resource_family', 'resource_abundance', 'resource_purity', 
    'resource_extraction_difficulty', 'resource_environmental_impact', 
    'resource_economic_value', 'resource_description',
    'biome_predators', 'biome_prey', 'biome_interaction_strengths'
]

# Note: current_stability is a STRING (e.g., "low", "medium", "high")
# Note: current_flow_direction is mostly empty
# Note: coral_* and current_u/v/speed are NUMERIC, not lists

def safe_parse_list(val):
    """Safely parse a string representation of a list into an actual list."""
    if pd.isna(val) or val == '':
        return []
    if isinstance(val, str):
        try:
            if val.startswith('[') and val.endswith(']'):
                return ast.literal_eval(val)
        except (ValueError, SyntaxError):
            pass
    return []

# Parse all list columns
for col in list_columns:
    if col in DF.columns:
        DF[col] = DF[col].apply(safe_parse_list)

class HighlightTilesInput(BaseModel):
    tiles: List[Dict[str, Any]] = Field(..., description="List of row/col dictionaries, optionally with color e.g. [{'row': 1, 'col': 2, 'color': [255, 0, 0]}, ...]")

@tool("highlight_tiles")
def highlight_tiles(tiles: List[Dict[str, Any]]):
    """
    Call this tool to highlight specific tiles on the user's map.
    Input should be a list of dictionaries, each with BOTH 'row' AND 'col' keys.
    Optional: 'color' key with [r, g, b] or [r, g, b, a] values (0-255).
    Example: [{'row': 10, 'col': 5}, {'row': 2, 'col': 3, 'color': [255, 0, 0]}]
    
    IMPORTANT: Each tile MUST have both 'row' and 'col' keys.
    """
    # Validate that each tile has both row and col
    validated_tiles = []
    for tile in tiles:
        if 'row' in tile and 'col' in tile:
            t = {'row': int(tile['row']), 'col': int(tile['col'])}
            if 'color' in tile:
                t['color'] = tile['color']
            validated_tiles.append(t)
        else:
            print(f"Warning: Skipping invalid tile (missing row or col): {tile}")
    
    if len(validated_tiles) == 0:
        return "Error: No valid tiles provided. Each tile must have both 'row' and 'col' keys."
    
    # Return the validated tiles as a string repr so the agent loop can capture it in the ToolMessage
    return str(validated_tiles)

@tool("query_data")
def query_data(code: str):
    """
    Executes Python code to query and analyze the 'df' pandas DataFrame.
    Use this tool to get information, statistics, or answers WITHOUT highlighting tiles.
    
    The dataframe 'df' has columns like: 'row', 'col', 'depth_m', 'biome', 'resource_economic_value', etc.
    
    You MUST assign the final result to a variable named 'result'.
    'result' can be a string, number, list, or any data you want to return to the user.
    
    Example code:
    # Count tiles below certain depth
    count = len(df[df['depth_m'] > 3000])
    result = f"There are {count} tiles deeper than 3000m"
    
    # Find max depth
    result = f"Maximum depth is {df['depth_m'].max()}m"
    
    # Get statistics
    df['total_econ'] = df['resource_economic_value'].apply(lambda x: sum(x) if len(x) > 0 else 0)
    result = f"Average economic value: {df['total_econ'].mean():.2f}"
    """
    local_vars = {'df': DF, 'pd': pd}
    print(f"[query_data] Executing:\n{code}")
    
    try:
        exec(code, {}, local_vars)
        if 'result' not in local_vars:
            return "ERROR: Code did not assign 'result' variable."
        
        result = local_vars['result']
        return str(result)
    except Exception as e:
        return f"ERROR: {str(e)}"

@tool("query_and_highlight")
def query_and_highlight(code: str):
    """
    Executes Python code to query the 'df' DataFrame and AUTOMATICALLY highlights the resulting tiles.
    Use this tool when you want to find AND highlight specific tiles on the map.
    
    The dataframe 'df' has columns like: 'row', 'col', 'depth_m', 'biome', 'resource_economic_value', etc.
    
    You MUST assign the final result to a variable named 'result_rows'.
    'result_rows' MUST be a list of dictionaries with BOTH 'row' AND 'col' keys.
    Optionally include 'color' key: [r, g, b] or [r, g, b, a].
    Example: [{'row': 1, 'col': 2, 'color': [255,0,0]}, {'row': 3, 'col': 4}]
    
    The tiles will be AUTOMATICALLY highlighted. You only need to return the row/col pairs.
    
    Example code:
    # Find top 5 richest tiles
    df['total_econ'] = df['resource_economic_value'].apply(lambda x: sum(x) if len(x) > 0 else 0)
    top_5 = df.nlargest(5, 'total_econ')
    result_rows = top_5[['row', 'col']].to_dict('records')
    
    # Find all tiles deeper than 3000m
    deep_tiles = df[df['depth_m'] > 3000]
    result_rows = deep_tiles[['row', 'col']].to_dict('records')
    """
    local_vars = {'df': DF, 'pd': pd}
    print(f"[query_and_highlight] Executing:\n{code}")
    
    try:
        exec(code, {}, local_vars)
        
        if 'result_rows' not in local_vars:
            return "ERROR: Code did not assign 'result_rows' variable."
        
        result_rows = local_vars['result_rows']
        
        if not isinstance(result_rows, list):
            return f"ERROR: result_rows must be a list, got {type(result_rows).__name__}"
        
        if len(result_rows) == 0:
            return "SUCCESS: Query executed but returned 0 tiles (nothing to highlight)"
        
        # Validate each tile has row and col
        validated_tiles = []
        for tile in result_rows:
            if isinstance(tile, dict) and 'row' in tile and 'col' in tile:
                try:
                    t = {'row': int(tile['row']), 'col': int(tile['col'])}
                    if 'color' in tile:
                        t['color'] = tile['color']
                    validated_tiles.append(t)
                except (ValueError, TypeError):
                    pass
        
        if len(validated_tiles) == 0:
            return f"ERROR: No valid tiles. Each tile must have 'row' and 'col' keys. Got: {result_rows[:3]}"
        
        # Return special format that main.py will parse for highlighting
        return f"HIGHLIGHT:{str(validated_tiles)}"
        
    except Exception as e:
        return f"ERROR: {str(e)}"

TOOLS = [query_data, query_and_highlight, highlight_tiles]

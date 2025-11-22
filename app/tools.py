import pandas as pd
import ast
from langchain.tools import tool
from pydantic import BaseModel, Field
from typing import List, Dict, Any

# Load data once for the tools
DF = pd.read_csv('merged.csv')

# Parse list columns from strings to actual lists
list_columns = [
    'hazard_type', 'hazard_severity', 'hazard_notes',
    'life_species', 'life_avg_depth_m', 'life_density', 'life_threat_level', 
    'life_behavior', 'life_trophic_level', 'life_prey_species',
    'poi_id', 'poi_category', 'poi_label', 'poi_description', 'poi_research_value',
    'resource_type', 'resource_family', 'resource_abundance', 'resource_purity', 
    'resource_extraction_difficulty', 'resource_environmental_impact', 
    'resource_economic_value', 'resource_description',
    'coral_coral_cover_pct', 'coral_health_index', 'coral_bleaching_risk', 'coral_biodiversity_index',
    'current_u_mps', 'current_v_mps', 'current_speed_mps', 'current_stability', 'current_flow_direction',
    'biome_predators', 'biome_prey', 'biome_interaction_strengths'
]

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
    tiles: List[Dict[str, int]] = Field(..., description="List of row/col dictionaries, e.g. [{'row': 1, 'col': 2}, ...]")

@tool("highlight_tiles")
def highlight_tiles(tiles: List[Dict[str, int]]):
    """
    Call this tool to highlight specific tiles on the user's map.
    Input should be a list of dictionaries, each with 'row' and 'col' keys.
    Example: [{'row': 10, 'col': 5}, {'row': 2, 'col': 3}]
    """
    # Return the tiles as a string repr so the agent loop can capture it in the ToolMessage
    return str(tiles)

class PythonQueryInput(BaseModel):
    code: str = Field(..., description="Python pandas code to execute. Variable 'df' is available. Must assign result to variable 'result_rows' as a list of dicts [{'row':..., 'col':...}].")

@tool("query_data")
def query_data(code: str):
    """
    Executes Python code to query the 'df' pandas DataFrame. 
    The dataframe 'df' has columns like: 'row', 'col', 'depth_m', 'biome', 'life_species' (list as string).
    
    You MUST assign the final result to a variable named 'result_rows'.
    'result_rows' must be a list of dictionaries, e.g. [{'row': 1, 'col': 2}].
    
    Example code:
    top_10 = df.head(10)
    result_rows = top_10[['row', 'col']].to_dict('records')
    """
    local_vars = {'df': DF}
    print(code)
    try:
        exec(code, {}, local_vars)
        if 'result_rows' in local_vars:
            return local_vars['result_rows']
        return "Error: Code did not assign 'result_rows' variable."
    except Exception as e:
        return f"Execution Error: {e}"

TOOLS = [query_data, highlight_tiles]

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import csv
import json
import os
import ast
from typing import AsyncGenerator
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

# --- AGENT SETUP ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    print("GOOGLE_API_KEY not found in environment variables!")

def initialize_agent():
    model = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=GOOGLE_API_KEY,
        thinking_budget=-1,
    )

    checkpointer = MemorySaver()

    agent = create_agent(
        model=model,
        tools=TOOLS,
        checkpointer=checkpointer,
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
            
                if msg_type == "text" and metadata.get("langgraph_node") == "model":
                    yield json.dumps({"type": "text", "content": message["text"]}) + "\n"
                elif msg_type == "tool_call":
                    if message.get("name") == "highlight_tiles":
                        try:
                            args = message.get("args", {})
                            tiles = args.get("tiles", [])
                            if tiles:
                                yield json.dumps({"type": "highlight", "tiles": tiles}) + "\n"
                        except Exception as e:
                            print(f"Error parsing tool call args: {e}")
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

@app.post("/api/clear")
async def clear_conversation():
    global thread_id
    thread_id += 1
    return {"status": "cleared"}

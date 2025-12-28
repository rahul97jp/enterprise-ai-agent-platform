"""
Main API Entry Point
--------------------
This module defines the FastAPI application server.
It handles file uploads, chat streaming (with tool events), and file downloads.
"""

import os
import shutil
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

# Internal imports
from agent import get_agent_graph, initialize_agent

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MCP_DATA_DIR = os.path.join(BASE_DIR, "mcp-server", "data")

# Ensure storage directory exists
os.makedirs(MCP_DATA_DIR, exist_ok=True)

# --- LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for the FastAPI app.
    Initializes the AI agent graph on startup to cache resources.
    """
    logger.info("System Startup: Initializing AI Agents...")
    await initialize_agent()
    yield
    logger.info("System Shutdown.")


app = FastAPI(title="Enterprise AI Assistant API", lifespan=lifespan)


# MIDDLEWARE
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# DATA MODELS
class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"


# ENDPOINTS

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Uploads a file to the MCP data directory.
    Useful for providing context (RFPs, PDFs) to the agent.
    """
    try:
        file_location = os.path.join(MCP_DATA_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"File uploaded successfully: {file.filename}")
        return {
            "filename": file.filename, 
            "status": "uploaded", 
            "path": file_location
        }
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")


@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Main Chat Endpoint.
    Streams agent responses and tool usage events using Server-Sent Events (SSE).
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # 1. Retrieve the cached agent graph
            graph = await get_agent_graph()
            
            # 2. Configure session memory
            config = {"configurable": {"thread_id": request.session_id}}
            
            # 3. Stream events (v2 API for granular control)
            async for event in graph.astream_events(
                {"messages": [HumanMessage(content=request.message)]}, 
                config=config,
                version="v2"
            ):
                kind = event["event"]
                
                # CASE A: LLM Text Streaming
                if kind == "on_chat_model_stream":
                    if "chunk" not in event["data"]:
                        continue
                        
                    chunk = event["data"]["chunk"]
                    
                    # Handle both Object-style and Dict-style chunks
                    content = ""
                    if hasattr(chunk, "content"):
                        content = chunk.content
                    elif isinstance(chunk, dict) and "content" in chunk:
                        content = chunk["content"]
                    
                    # Gemini/LLM Compatibility Fix: Flatten content lists
                    final_text = ""
                    if isinstance(content, list):
                        for part in content:
                            if isinstance(part, dict) and "text" in part:
                                final_text += part["text"]
                            elif isinstance(part, str):
                                final_text += part
                    elif isinstance(content, str):
                        final_text = content
                    
                    if final_text:
                        yield json.dumps({
                            "type": "agent", 
                            "content": final_text
                        }) + "\n"
                        
                # CASE B: Tool Execution Events
                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    # Filter out internal LangGraph tools (prefixed with _)
                    if tool_name and not tool_name.startswith("_"):
                        yield json.dumps({
                            "type": "tool", 
                            "content": f"Accessed Tool: {tool_name}"
                        }) + "\n"

        except Exception as e:
            logger.error(f"Stream Error: {e}")
            yield json.dumps({"type": "error", "content": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Serves generated PDF files for download.
    Includes security check to prevent directory traversal.
    """
    if ".." in filename or "/" in filename:
        logger.warning(f"Invalid file access attempt: {filename}")
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    file_path = os.path.join(MCP_DATA_DIR, filename)
    
    if not os.path.exists(file_path):
        logger.warning(f"Download requested for non-existent file: {filename}")
        raise HTTPException(status_code=404, detail="File not found")
        
    logger.info(f"Serving file download: {filename}")
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
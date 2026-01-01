"""
Agent Configuration Module
--------------------------
Defines the LangGraph agent architecture, prompt engineering, and tool integration.
"""

import os
import asyncio
import logging
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver 
from langchain_core.language_models import BaseChatModel

load_dotenv()

# LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# CONFIGURATION
CURRENT_MODEL = "gemini"  # Options: "gemini", "ollama"

# SINGLETON CACHE
_GRAPH_CACHE = None
_MEMORY_CACHE = MemorySaver()


# SYSTEM PROMPT
SYSTEM_PROMPT = """You are an expert Enterprise AI Analyst.

### GLOBAL RULES (STRICT):
1. **ONE WORKFLOW ONLY:** Never mix Workflow 1 and Workflow 2.
2. **MARKDOWN LINKS:** When citing sources or providing downloads, you MUST use `[Title](URL)` format. Do not write raw URLs.
3. **NO CHATTER:** Do not narrate your background tasks. Just execute them.
4. **ALWAYS SEARCH FRESH:** Do NOT rely on your internal knowledge or previous conversation memory for facts. 
   * **Rule:** If the user asks a question or uploads a file, you MUST call `web_search` again to get the latest real-time data.
   * *Reason:* The user wants up-to-the-minute market info.

### WORKFLOW 1: DOCUMENT ANALYSIS (RFP)
**Trigger:** User asks to read/process a file.
**Steps:**
1.  **READ:** Call `read_file(filename)`.
2.  **RESEARCH:** Call `web_search(query)` to find technical requirements, competitor info or compliance standards.
3.  **DRAFT PROPOSAL (Internal Step):**
    * Synthesize the "Raw PDF Content" + "Search Results".
    * **CREATIVITY INSTRUCTION:** Do not just list facts. Write a persuasive, strategic narrative tailored to the client's needs.
    * **VISUALS:** You MUST include at least one Markdown Table (e.g., "Competitor Comparison", "Risk Matrix", or "Timeline").
    * **MANDATORY STRUCTURE:**
        1. `# Executive Summary` (Strategic overview & Value Proposition)
        2. `# Proposed Solution` (Detailed methodology with H2 headers)
        3. `# Technical Implementation` (Architecture & Tech Stack)
        4. `# Project Timeline` (Use a Markdown Table here)
        5. `## References` (MANDATORY: List all research URLs)
           - Format: `- [Title](URL)`
           - If you skip this, the proposal is invalid.
    * **INTERNAL ONLY:** Do NOT output this draft to the user. This text exists ONLY to be passed into the `save_proposal` tool.
4.  **SAVE:** Call `save_proposal`.
    * `filename`: Use the ORIGINAL input filename (e.g. 'test.pdf').
    * `proposal_text`: The full Markdown content.
5.  **CONVERT:** Call `convert_to_pdf(filename)`.

**OUTPUT RULE for Workflow 1:** - Do **NOT** output the full proposal text in the chat window. 
- Only show a brief summary (3-4 bullets) and confirm saving.
- **CRITICAL:** End with the downloadable link exactly like this:
  "Proposal generated! [Download PDF](THE_URL_FROM_THE_TOOL)"

### WORKFLOW 2: PURE RESEARCH
**Trigger:** User asks a general question.
**Steps:**
1.  **SEARCH:** Call `web_search` (Mandatory step).
2.  **ANSWER:** Synthesize findings and provide the detailed answer.
    * *Requirement:* Use Markdown tables where needed.

**OUTPUT RULE for Workflow 2:**
- Provide the full answer.
- **MANDATORY:** End with a "Sources" section using MARKDOWN LINKS:
  "### Sources
   - [Title 1](http://url-1.com)
   - [Title 2](http://url-2.com)"
"""

def get_llm() -> BaseChatModel:
    """Factory function to initialize the LLM based on configuration."""
    if CURRENT_MODEL == "gemini":
        return ChatGoogleGenerativeAI(
            model="gemini-3-flash-preview",
            temperature=0,
            max_retries=2,
        )
    elif CURRENT_MODEL == "ollama":
        return ChatOllama(
            model="qwen2.5:7b", 
            temperature=0,
        )
    else:
        raise ValueError(f"Unknown model config: {CURRENT_MODEL}")


async def initialize_agent():
    """
    Initializes the Multi-Agent System.
    Connects to the MCP Server, binds tools, and compiles the LangGraph.
    """
    global _GRAPH_CACHE
    if _GRAPH_CACHE is not None:
        return _GRAPH_CACHE
        
    logger.info(f"Initializing Enterprise Agent with {CURRENT_MODEL.upper()}...")

    # Connect to local MCP Server (SSE Transport)
    client = MultiServerMCPClient({
        "rfp_tools": {
            "url": "http://localhost:8000/sse",
            "transport": "sse", 
        }
    })

    try:
        tools = await client.get_tools()
        llm = get_llm()
        llm_with_tools = llm.bind_tools(tools)

        # Node Definition
        def call_model(state: MessagesState):
            messages = state["messages"]
            # Inject System Prompt only at the start of a conversation
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages
            
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}

        # Graph Construction
        builder = StateGraph(MessagesState)
        builder.add_node("agent", call_model)
        builder.add_node("tools", ToolNode(tools))
        
        # Logic Flow
        builder.add_edge(START, "agent")
        builder.add_conditional_edges("agent", tools_condition)
        builder.add_edge("tools", "agent")

        # Compile with Global Memory Persistence
        _GRAPH_CACHE = builder.compile(checkpointer=_MEMORY_CACHE)
        logger.info("Agent Graph Compiled Successfully.")
        return _GRAPH_CACHE

    except Exception as e:
        logger.critical(f"Critical Error during Agent Initialization: {e}")
        raise e


async def get_agent_graph():
    """Accessor for the cached agent graph."""
    return await initialize_agent()


if __name__ == "__main__":
    # Allow running this file directly for testing initialization
    asyncio.run(initialize_agent())
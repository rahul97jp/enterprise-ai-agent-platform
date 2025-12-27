# Enterprise AI Assistant

An agentic platform designed to automate complex document analysis and research tasks. This system leverages **LangGraph** for state management and the **Model Context Protocol (MCP)** to modularize tool execution, enabling an LLM to read RFPs, perform live web research, and generate strategic PDF proposals.

![Project Screenshot](https://via.placeholder.com/1200x600?text=Enterprise+AI+Assistant+Screenshot)
*(Replace this link with your actual screenshot)*

## 🚀 Key Capabilities

* **RFP Analysis Workflow:** Ingests PDF documents, extracts requirements, performs competitor research via Tavily, and drafts a structured response.
* **Deep Research Agent:** A ReAct-based agent that performs multi-step reasoning. It refuses to rely on stale training data, forcing fresh web searches for every query.
* **PDF Generation:** Automates the creation of professional PDF deliverables with CSS-styled formatting, bullet points, and citations.
* **Memory & Context:** Uses `MemorySaver` to maintain conversational context across multiple turns (persisted via Session ID).
* **Tool Isolation (MCP):** Tools (Read, Search, Save) are hosted on a separate FastMCP server. The backend connects via `MultiServerMCPClient`, ensuring a decoupled and scalable architecture.

## 🛠️ Tech Stack

### Backend (Agent Orchestration)
* **Python 3.11+** (Managed via `uv`)
* **LangGraph:** State machine and cyclic graph architecture.
* **LangChain:** LLM interface (Google Gemini / Ollama).
* **MultiServerMCPClient:** Connects the agent to the MCP tools server via SSE.
* **FastAPI:** Async REST API with Server-Sent Events (SSE) for streaming.

### MCP Server (Tools Layer)
* **FastMCP:** Lightweight protocol implementation.
* **PyMuPDF4LLM:** High-fidelity PDF parsing.
* **Tavily API:** Optimized search for LLM agents.
* **XHTML2PDF:** HTML-to-PDF conversion engine.

### Frontend
* **Next.js 14** (App Router).
* **Tailwind CSS** + **Typography Plugin**.
* **Lucide React:** Icons.

## ⚡ Quick Start

### 1. Prerequisites
* Python 3.11 or higher
* Node.js 18+
* `uv` (Python package manager)
* Google Gemini API Key & Tavily API Key

### 2. Environment Setup
Create a `.env` file in the root directory:
```bash
GOOGLE_API_KEY=your_google_key
TAVILY_API_KEY=your_tavily_key
# Optional: DEBUG=true
```

### 3. Installation
**Backend & MCP:**
```bash
# Option A: Using uv (Recommended)
uv sync
# Option B: Using standard pip
pip install -r requirements.txt
```

**Frontend:**
```bash
cd frontend
npm install
```

### Running the System
* You need to run three separate processes in three terminal windows.

**Terminal 1: MCP Tool Server**
```bash
uv run mcp-server/src/server.py
```
# Expected Output: Starting MCP Server via SSE...

**Terminal 2: Backend API**
```bash
uv run backend/main.py
# Expected Output: Uvicorn running on http://0.0.0.0:8001
```

**Terminal 3: Frontend UI**
```bash
cd frontend
npm run dev
```

* **Open your browser to http://localhost:3000**
"""
MCP Server Module
-----------------
Exposes tools for file operations, web research, and PDF generation via the Model Context Protocol.
"""

import os
import re
import logging
import markdown
from xhtml2pdf import pisa
from mcp.server.fastmcp import FastMCP
from tavily import TavilyClient
from dotenv import load_dotenv

# Internal Utility Imports
from pdf_utils import parse_pdf_to_markdown, list_rfp_files
from db_utils import init_db, add_project, update_status

load_dotenv()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Initialize Third-Party Clients
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
tavily = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None

if not tavily:
    logger.warning("TAVILY_API_KEY not found. Web search tool will fail.")

# Initialize MCP Server
mcp = FastMCP(
    "RFPToolkit",
    host="0.0.0.0",
    port=8000,
    dependencies=["pymupdf4llm", "tavily-python", "python-dotenv", "xhtml2pdf", "markdown"]
)

# Initialize Database & Filesystem
try:
    init_db()
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.info(f"Server initialized. Data directory: {DATA_DIR}")
except Exception as e:
    logger.critical(f"Failed to initialize server environment: {e}")
    raise e


# 1. HELPER FUNCTIONS (MARKDOWN PRE-PROCESSING)

def fix_markdown_lists(text: str) -> str:
    """
    Inserts a blank line before list items (*, -, 1.) if the preceding line 
    is a paragraph. This ensures xhtml2pdf renders lists correctly.
    """
    lines = text.split('\n')
    new_lines = []
    
    # Regex: Matches list start (*, -, 1.) followed by space
    list_pattern = re.compile(r'^\s*([\*\-]|\d+\.)\s+')
    # Regex: Matches empty lines or headers
    non_text_pattern = re.compile(r'^\s*$|^#')

    for i, line in enumerate(lines):
        is_list = list_pattern.match(line)
        
        if is_list and i > 0:
            prev_line = lines[i-1]
            # If prev line is text (not empty/header/list), force blank line
            if not non_text_pattern.match(prev_line) and not list_pattern.match(prev_line):
                new_lines.append('') 
        
        new_lines.append(line)
        
    return '\n'.join(new_lines)


def fix_markdown_tables(text: str) -> str:
    """
    Inserts blank lines around markdown tables (detected by pipe characters)
    to prevent rendering issues in the PDF parser.
    """
    lines = text.split('\n')
    new_lines = []
    # Regex: Matches lines starting and ending with pipe |
    table_pattern = re.compile(r'^\s*\|.*\|.*\|\s*$')

    for i, line in enumerate(lines):
        if table_pattern.match(line):
            # If prev line was text (not table/empty), add space
            if i > 0 and lines[i-1].strip() != '' and not table_pattern.match(lines[i-1]):
                new_lines.append('')
        
        new_lines.append(line)
        
    return '\n'.join(new_lines)


# 2. MCP TOOLS

@mcp.tool()
def list_files() -> str:
    """Lists all PDF files currently stored in the data directory."""
    logger.info("Tool called: list_files")
    files = list_rfp_files(DATA_DIR)
    return "\n".join(files) if files else "No files found."


@mcp.tool()
def read_file(filename: str) -> str:
    """
    Reads and extracts text content from a PDF file.
    
    Args:
        filename: The exact filename (e.g., 'test.pdf').
    """
    logger.info(f"Tool called: read_file for '{filename}'")
    file_path = os.path.join(DATA_DIR, filename)
    
    try:
        # Register project in DB for tracking
        add_project(filename)
        logger.info(f"DB: Registered project '{filename}'")
    except Exception as e:
        logger.error(f"DB Registration failed for {filename}: {e}")
        
    return parse_pdf_to_markdown(file_path)


@mcp.tool()
def web_search(query: str) -> str:
    """
    Performs an advanced web search for technical information.
    
    Args:
        query: The search string.
    """
    if not tavily:
        return "Error: TAVILY_API_KEY is missing or invalid."
    
    logger.info(f"Tool called: web_search for query '{query}'")
    
    try:
        response = tavily.search(query=query, search_depth="advanced", max_results=3)
        results = []

        # DEBUG LOGGING
        if os.getenv("DEBUG") == "true":
            print(f"\n--- DEBUG: SEARCH RESULTS FOR '{query}' ---")
            for i, res in enumerate(response.get('results', [])):
                print(f"Result #{i+1}: {res['title']}")
                print(f"URL: {res['url']}")
                print(f"Snippet: {res['content'][:150]}...") 
                print("-" * 40)
            print("--- END DEBUG ---\n")
            
        for res in response.get('results', []):
            entry = (
                f"SOURCE_TITLE: {res['title']}\n"
                f"SOURCE_URL: {res['url']}\n"
                f"CONTENT: {res['content']}\n"
            )
            results.append(entry)
        
        logger.info(f"Search successful. Found {len(results)} results.")
        return f"Found {len(results)} results.\n\n" + "\n---\n".join(results)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Search Error: {str(e)}"


@mcp.tool()
def save_proposal(filename: str, proposal_text: str) -> str:
    """
    Saves a generated proposal to disk and updates the database status.
    
    Args:
        filename: The ORIGINAL input filename.
        proposal_text: The complete Markdown content.
    """
    logger.info(f"Tool called: save_proposal for '{filename}'")
    
    # Normalize filename
    base_name = filename.replace("Proposal_for_", "").replace(".md", "").replace(".pdf", "")
    disk_filename = f"Proposal_for_{base_name}.md"
    save_path = os.path.join(DATA_DIR, disk_filename)
    
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(proposal_text)
        logger.info(f"File saved to disk: {disk_filename}")
    except IOError as e:
        logger.error(f"Disk save failed: {e}")
        return f"Error saving file to disk: {e}"

    # Update Database
    db_msg = update_status(filename, "COMPLETED", proposal_text)
    logger.info(f"DB Update: {db_msg}")
    
    return f"Saved proposal to {disk_filename}. {db_msg}"


@mcp.tool()
def convert_to_pdf(filename: str) -> str:
    """
    Converts a saved Markdown proposal into a downloadable PDF.
    
    Args:
        filename: The filename used in save_proposal.
    """
    logger.info(f"Tool called: convert_to_pdf for '{filename}'")
    
    # Normalize filename
    base_name = filename.replace("Proposal_for_", "").replace(".md", "").replace(".pdf", "")
    md_path = os.path.join(DATA_DIR, f"Proposal_for_{base_name}.md")
    
    if not os.path.exists(md_path):
        logger.error(f"Markdown file not found: {md_path}")
        return f"Error: Markdown file {md_path} not found. Ensure save_proposal was called first."

    try:
        with open(md_path, "r", encoding="utf-8") as f:
            md_text = f.read()

        # PRE-PROCESSING
        md_text = fix_markdown_lists(md_text)
        md_text = fix_markdown_tables(md_text)

        # LINKS FIX
        url_pattern = r'(?<!\]\()(?<!=")(https?://[^\s\)]+)'
        md_text = re.sub(url_pattern, lambda m: f'[{m.group(0)}]({m.group(0)})', md_text)

        # HTML GENERATION
        html_body = markdown.markdown(md_text, extensions=['extra', 'codehilite'])

        # PDF STYLING
        full_html = f"""
        <html>
        <head>
            <style>
                @page {{
                    size: letter;
                    margin: 2cm;
                    @frame footer_frame {{
                        -pdf-frame-content: footerContent;
                        bottom: 1cm;
                        margin-left: 1cm;
                        margin-right: 1cm;
                        height: 1cm;
                    }}
                }}
                
                body {{ font-family: Helvetica, sans-serif; font-size: 11px; line-height: 1.5; color: #222; }}
                
                h1 {{ color: #2c3e50; font-size: 24px; border-bottom: 2px solid #2c3e50; margin-top: 30px; margin-bottom: 15px; }}
                h2 {{ color: #2980b9; font-size: 16px; margin-top: 20px; border-bottom: 1px solid #eee; margin-bottom: 10px; }}
                h3 {{ color: #34495e; font-size: 13px; font-weight: bold; margin-top: 15px; margin-bottom: 5px; }}
                
                p {{ margin-bottom: 10px; text-align: justify; }}
                
                ul {{ margin-top: 0; margin-bottom: 10px; padding-left: 20px; }}
                li {{ list-style-type: disc; margin-bottom: 5px; }}
                
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; border: 1px solid #ddd; }}
                th {{ background-color: #f8fafc; border: 1px solid #cbd5e1; padding: 8px; text-align: left; font-weight: bold; font-size: 10px; }}
                td {{ border: 1px solid #cbd5e1; padding: 8px; font-size: 10px; }}
                tr:nth-child(even) {{ background-color: #f1f5f9; }}
                
                a {{ color: #0066cc; text-decoration: none; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border: 1px solid #ddd; font-family: Courier, monospace; white-space: pre-wrap; }}
            </style>
        </head>
        <body>
            {html_body}
            <div id="footerContent" style="text-align:center; font-size: 9px; color: #888;">
                Generated by RFP Agent Platform • Page <pdf:pagenumber>
            </div>
        </body>
        </html>
        """
        
        pdf_filename = f"Proposal_for_{base_name}.pdf"
        pdf_path = os.path.join(DATA_DIR, pdf_filename)
        
        # PDF CREATION
        with open(pdf_path, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(src=full_html, dest=pdf_file)

        if pisa_status.err:
            logger.error(f"PDF generation error: {pisa_status.err}")
            return f"Error generating PDF: {pisa_status.err}"
        
        logger.info(f"PDF generated successfully: {pdf_filename}")
        
        # Return Download URL (Hardcoded localhost for dev; ideally configured via ENV)
        return f"http://localhost:8001/download/{pdf_filename}"

    except Exception as e:
        logger.critical(f"Critical error during PDF conversion: {e}")
        return f"Unexpected Error during PDF conversion: {str(e)}"


if __name__ == "__main__":
    logger.info("Starting MCP Server via SSE...")
    mcp.run(transport="sse")
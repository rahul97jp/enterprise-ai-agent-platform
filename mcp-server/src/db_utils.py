"""
Database Utility Module
-----------------------
Manages SQLite interactions for tracking RFP projects, file status, and generated proposals.
Includes robust fallback logic for matching filenames to database records.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional

# Constants
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "rfp_platform.db")


def get_db_connection() -> sqlite3.Connection:
    """Creates and returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    """
    Initializes the database schema if it does not exist.
    Creates the 'projects' table for tracking file processing status.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            status TEXT DEFAULT 'UPLOADED',
            proposal_content TEXT,
            created_at TEXT
        )
    ''')
    conn.commit()
    conn.close()


def add_project(filename: str) -> None:
    """
    Registers a new project or updates an existing one to 'PROCESSING'.
    
    Args:
        filename: The name of the file being processed.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check for existing record
    c.execute("SELECT id FROM projects WHERE filename = ?", (filename,))
    existing = c.fetchone()
    
    timestamp = datetime.now().isoformat()
    
    if existing:
        # Reset status for re-processing
        c.execute(
            "UPDATE projects SET status='PROCESSING', created_at=? WHERE id=?", 
            (timestamp, existing[0])
        )
    else:
        # Create new record
        c.execute(
            "INSERT INTO projects (filename, status, created_at) VALUES (?, ?, ?)", 
            (filename, 'PROCESSING', timestamp)
        )
        
    conn.commit()
    conn.close()


def update_status(filename: str, status: str, proposal: Optional[str] = None) -> str:
    """
    Updates the status and content of a project.
    Includes fallback logic to handle filename mismatches (e.g., if LLM modifies the name).
    
    Args:
        filename: The filename to update.
        status: The new status (e.g., 'COMPLETED').
        proposal: Optional generated proposal content.
        
    Returns:
        A status message indicating success or failure.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Attempt Exact Match Update
    if proposal:
        c.execute(
            "UPDATE projects SET status = ?, proposal_content = ? WHERE filename = ?", 
            (status, proposal, filename)
        )
    else:
        c.execute(
            "UPDATE projects SET status = ? WHERE filename = ?", 
            (status, filename)
        )
    
    rows_affected = c.rowcount
    
    # 2. Fallback Logic: Match most recent 'PROCESSING' record
    # This handles cases where the LLM passes a derived filename (e.g., 'Proposal_Doc.pdf')
    # instead of the original 'Doc.pdf'.
    if rows_affected == 0 and status == "COMPLETED":
        c.execute(
            "SELECT filename FROM projects WHERE status='PROCESSING' ORDER BY id DESC LIMIT 1"
        )
        fallback = c.fetchone()
        
        if fallback:
            real_filename = fallback[0]
            if proposal:
                c.execute(
                    "UPDATE projects SET status = ?, proposal_content = ? WHERE filename = ?", 
                    (status, proposal, real_filename)
                )
            rows_affected = c.rowcount

    conn.commit()
    conn.close()
    
    if rows_affected == 0:
        return f"Warning: Database update failed. Project '{filename}' not found."
    return "Database updated successfully."
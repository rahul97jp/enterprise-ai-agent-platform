"""
PDF Processing Utilities
------------------------
Helper functions for extracting text from PDF documents using PyMuPDF (pymupdf4llm).
"""

import pymupdf4llm
import os
from typing import List

def parse_pdf_to_markdown(file_path: str) -> str:
    """
    Extracts text from a PDF and converts it to Markdown format.
    
    Args:
        file_path: Absolute path to the PDF file.
        
    Returns:
        A string containing the markdown representation of the PDF content.
        Returns an error message string if the file is missing or parsing fails.
    """
    if not os.path.exists(file_path):
        return f"Error: File not found at {file_path}"
    
    try:
        # pymupdf4llm extracts text with layout preservation
        md_text = pymupdf4llm.to_markdown(file_path)
        return md_text
    except Exception as e:
        return f"Error parsing PDF: {str(e)}"


def list_rfp_files(directory: str) -> List[str]:
    """
    Scans the data directory for PDF files.
    
    Args:
        directory: The directory path to scan.
        
    Returns:
        A list of filenames ending in .pdf.
    """
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        return []
        
    return [f for f in os.listdir(directory) if f.lower().endswith('.pdf')]
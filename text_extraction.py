# processing/text_extraction.py (Refactored Version)

import io
import re
import asyncio
from typing import List

from fastapi import HTTPException
from PyPDF2 import PdfReader
from docx import Document
from pdf2image import convert_from_bytes
import pytesseract

def preprocess_pages(pages: List[str]) -> str:
    """
    Cleans text by removing headers, footers, and other noise.
    """
    full_text = "\n".join(pages)

    block_patterns_to_remove = [
        r'(?:Signatories|Prepared\s+By)[\s\S]*?(?:Page\s+\d+\s+of\s+\d+|Status:\s*Draft\s*Approved|QAP:.*|Page\s+No\.:|NOT\s+TO\s+BE\s+COPIED)',
        r'REVISION\s+HISTORY[\s\S]*?(?:Page\s+\d+\s+of\s+\d+|$)',
    ]
    master_block_regex = re.compile('|'.join(block_patterns_to_remove), re.IGNORECASE | re.DOTALL)
    cleaned_text = master_block_regex.sub(' ', full_text)
    
    line_patterns_to_remove = [
        r'^\s*(FDC\s+LIMITED|UMEDICA\s+LABORATORIES|ORBICULAR\s+PHARMA|VEE\s+EXCEL\s+DRUGS|GRACURE|FDC|MEVAC|VXL)\s*.*$',
        r'^\s*(STANDARD\s+OPERATING\s+PROCEDURE|CHANGE\s+HISTORY|ANNEXURE|FORMAT\s+OF\s+DEVIATION|QUALITY\s+ASSURANCE|PRODUCTION)\s*$',
        r'^\s*TITLE:.*$',
        r'^\s*(MASTER|TRAINING|UNCONTROLLED|CONTROLLED)\s+COPY\s*$',
        r'^\s*(SOP\s+Number|Effective\s+Date|Review\s+Period|Review\s+Date|Supersede(?:s)?\s+No|Revision\s+No|Page\s+No|Department|Reference|Section|Annexure)\s*:.*$',
        r'^\s*(A1/SOP/QAD/\d+|Doc\.\s+No\.|Format\s+No\.)\s*.*$',
    ]
    master_line_regex = re.compile('|'.join(line_patterns_to_remove), re.IGNORECASE)

    good_lines = []
    for line in cleaned_text.split('\n'):
        stripped_line = line.strip()
        
        if not stripped_line or master_line_regex.match(stripped_line):
            continue
            
        # Relaxed: Only filter out lines that are purely numeric/special chars or very short
        # was: if not re.search(r'[a-zA-Z]{4,}', stripped_line):
        if not re.search(r'[a-zA-Z]{2,}', stripped_line) or len(stripped_line) < 10:
            continue
            
        good_lines.append(stripped_line)

    final_text = " ".join(good_lines)
    result = re.sub(r'\s+', ' ', final_text).strip()
    # print(f"DEBUG: preprocess_pages - Input lines: {len(pages)}, Output length: {len(result)} chars")
    if len(result) == 0 and len(full_text) > 0:
        # print("DEBUG: WARNING - All text was filtered out by cleaning logic!")
        pass
    return result

async def get_text_from_file_async(file_bytes: bytes, filename: str) -> List[str]:
    """Asynchronously extracts text from PDF (with OCR fallback) or DOCX files."""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    # with open("debug_log.txt", "a") as f:
    #     f.write(f"DEBUG: Filename='{filename}', Ext='{ext}'\n")
    page_texts = []
    if ext == 'pdf':
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            # print(reader)
            page_texts = [(p.extract_text() or "") for p in reader.pages]
            if sum(len(p.strip()) for p in page_texts) < 200:
                print("INFO: PyPDF2 extraction weak, falling back to Tesseract OCR...")
                # NOTE: Running blocking I/O (like file system access from pdf2image/tesseract)
                # in a separate thread to avoid blocking the event loop.
                loop = asyncio.get_running_loop()
                # Define the Poppler path explicitly
                POPPLER_PATH = r"C:\Users\26055\Desktop\poppler-25.12.0\Library\bin"
                # print(f"DEBUG: Using poppler path: {POPPLER_PATH}")
                ocr_pages = await loop.run_in_executor(
                    None, lambda: convert_from_bytes(file_bytes, dpi=300, poppler_path=POPPLER_PATH)
                )
                page_texts = [pytesseract.image_to_string(img) for img in ocr_pages]
        except Exception as e:
            if "PyCryptodome is required" in str(e):
                raise HTTPException(status_code=500, detail="PDF processing failed: This PDF is encrypted. Please install 'PyCryptodome'.")
            raise HTTPException(status_code=500, detail=f"PDF processing failed: {e}")
    elif ext in ['docx', 'doc']:
        doc = Document(io.BytesIO(file_bytes))
        page_texts = ["\n".join([p.text for p in doc.paragraphs if p.text.strip()])]
    elif ext == 'txt':
        page_texts = [file_bytes.decode("utf-8", errors="ignore")]
    if not any(p.strip() for p in page_texts):
        # print("DEBUG: get_text_from_file_async - No text extracted from file.")
        raise HTTPException(status_code=400, detail="Could not extract usable text.")
    # print(f"DEBUG: get_text_from_file_async - Extracted {sum(len(p) for p in page_texts)} chars from {len(page_texts)} pages.")
    return page_texts

# NOTE: The synchronous wrapper `get_text_from_file_sync` has been removed.
# The async endpoints now call `get_text_from_file_async` directly.
#!/usr/bin/env python3
"""ese_ocr.py - Download and OCR official UPSC ESE EE question papers (2017-2025) from upsc.gov.in.

Creates a SQLite database with provenance=official_pyq.
Source PDFs: upsc.gov.in (Previous Question Papers → Engineering Services).

Note: UPSC does not publish official answer keys on the live site (verified 2026-09-27).
answer_key will be empty for all rows.

Usage:
    python3 scripts/ese_ocr.py --download --parse --output ~/data/ese_official.sqlite
    python3 scripts/ese_ocr.py --parse-only --input-dir ~/AIR10_LIBRARY/official_pyq/ese_ee --output ~/data/ese_official.sqlite
"""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) required: pip install pymupdf")
    sys.exit(1)

try:
    import pytesseract
    from PIL import Image
except ImportError:
    print("pytesseract and Pillow required: pip install pytesseract pillow")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("requests required: pip install requests")
    sys.exit(1)

# UPSC ESE EE paper structure: 2017-2025, Paper-I (GS) + Paper-II (EE)
# URLs on upsc.gov.in change; this script searches the "Previous Question Papers" page
UPSC_BASE = "https://www.upsc.gov.in"
UPSC_PQP_URL = "https://www.upsc.gov.in/examinations/previous-question-papers"

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    exam TEXT NOT NULL,
    year INTEGER NOT NULL,
    organizer TEXT NOT NULL,
    section TEXT NOT NULL,  -- 'GS' or 'EE'
    qno TEXT NOT NULL,
    stem TEXT NOT NULL,
    options_json TEXT NOT NULL,
    answer_key TEXT,
    pdf TEXT NOT NULL,
    source_url TEXT NOT NULL,
    key_url TEXT,
    provenance TEXT NOT NULL DEFAULT 'official_pyq',
    sha256 TEXT
);
CREATE INDEX IF NOT EXISTS idx_questions_exam ON questions(exam);
CREATE INDEX IF NOT EXISTS idx_questions_year ON questions(year);
CREATE INDEX IF NOT EXISTS idx_questions_section ON questions(section);
"""

def find_ese_pdf_urls() -> dict:
    """Scrape upsc.gov.in for ESE EE PDF links. Returns {year: {section: url}}."""
    # This is a placeholder - real implementation needs to parse the UPSC page
    # UPSC URLs are dynamic; manual collection is more reliable
    print("WARNING: UPSC PDF URLs change yearly. Manual download recommended.")
    print("Visit: https://www.upsc.gov.in/examinations/previous-question-papers")
    print("Look for: Engineering Services Examination → Year → Paper-I (GS) / Paper-II (EE)")
    return {}

def download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF from URL."""
    try:
        headers = {"User-Agent": "awesome-electrical-exams/1.0 (+https://github.com/lakhidas168-ship-it)"}
        resp = requests.get(url, headers=headers, timeout=120, stream=True)
        resp.raise_for_status()
        
        with open(dest, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        
        if dest.stat().st_size < 10000:
            print(f"  WARNING: {dest} is very small ({dest.stat().st_size} bytes)")
            return False
        
        print(f"  Downloaded: {dest.name} ({dest.stat().st_size:,} bytes)")
        return True
    except Exception as e:
        print(f"  FAILED to download {url}: {e}")
        return False

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def ocr_pdf_halves(pdf_path: Path) -> list:
    """OCR a PDF by splitting pages into top/bottom halves (UPSC two-column layout).
    Returns list of page texts."""
    doc = fitz.open(pdf_path)
    texts = []
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Render page at high DPI for OCR
        mat = fitz.Matrix(3, 3)  # 3x zoom = ~216 DPI
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # Split into top and bottom halves (UPSC papers often have two columns)
        w, h = img.size
        top_half = img.crop((0, 0, w, h // 2))
        bottom_half = img.crop((0, h // 2, w, h))
        
        # OCR both halves
        top_text = pytesseract.image_to_string(top_half, config='--psm 6')
        bottom_text = pytesseract.image_to_string(bottom_half, config='--psm 6')
        
        texts.append((top_text, bottom_text))
    
    doc.close()
    return texts

def extract_questions_from_ocr_texts(texts: list, year: int, section: str, source_url: str, pdf_path: Path) -> list:
    """Extract questions from OCR'd text halves. Returns list of dicts."""
    questions = []
    
    # Join all text
    full_text = "\n".join(t[0] + "\n" + t[1] for t in texts)
    
    # UPSC ESE questions: Q.1, Q.2, etc. with options (a), (b), (c), (d) or (A), (B), (C), (D)
    # This pattern needs tuning per year
    q_pattern = re.compile(
        r'Q\.?\s*(\d+)[\.\s]+(.+?)(?:\n\s*[\(\[]([a-dA-D])[\)\]]\s*(.+?))?'
        r'(?:\n\s*[\(\[]([a-dA-D])[\)\]]\s*(.+?))?(?:\n\s*[\(\[]([a-dA-D])[\)\]]\s*(.+?))?(?:\n\s*[\(\[]([a-dA-D])[\)\]]\s*(.+?))?',
        re.DOTALL | re.MULTILINE | re.IGNORECASE
    )
    
    for match in q_pattern.finditer(full_text):
        qno = match.group(1)
        stem = match.group(2).strip() if match.group(2) else ""
        
        # Collect options
        opts = {'a': '', 'b': '', 'c': '', 'd': ''}
        for i in range(3, 11, 2):
            if match.group(i) and match.group(i+1):
                opt_letter = match.group(i).lower()
                opt_text = match.group(i+1).strip()
                if opt_letter in opts:
                    opts[opt_letter] = opt_text
        
        if stem and any(opts.values()):
            questions.append({
                'id': f"ESE{year}_{section}_{qno}",
                'exam': '|ese|',
                'year': year,
                'organizer': 'UPSC',
                'section': section,
                'qno': qno,
                'stem': stem[:2000],
                'options_json': json.dumps(opts),
                'answer_key': '',  # UPSC doesn't publish keys on live site
                'pdf': str(pdf_path),
                'source_url': source_url,
                'key_url': '',
                'provenance': 'official_pyq',
            })
    
    return questions

def build_database(output_path: Path, input_dir: Path = None, download: bool = False):
    """Build the official UPSC ESE EE PYQ database."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(output_path)
    conn.executescript(SCHEMA)
    
    total_questions = 0
    
    for year in range(2017, 2026):
        for section in ['GS', 'EE']:
            pdf_name = f"ESE{year}_P{'1' if section == 'GS' else '2'}_{section}.pdf"
            pdf_path = None
            
            if download:
                # UPSC URLs are not stable; this is a placeholder
                print(f"WARNING: Auto-download for UPSC ESE {year} {section} not implemented.")
                print(f"  Manually download from upsc.gov.in and place at: {input_dir or 'input_dir'}/{pdf_name}")
                continue
            elif input_dir:
                candidates = list(input_dir.glob(f"*{year}*P{'1' if section == 'GS' else '2'}*{section}*.pdf"))
                if candidates:
                    pdf_path = candidates[0]
            
            if pdf_path and pdf_path.exists():
                print(f"OCR processing ESE {year} {section}...")
                texts = ocr_pdf_halves(pdf_path)
                questions = extract_questions_from_ocr_texts(texts, year, section, UPSC_PQP_URL, pdf_path)
                
                sha = sha256_file(pdf_path)
                for q in questions:
                    q['sha256'] = sha
                    try:
                        conn.execute("""
                            INSERT OR REPLACE INTO questions 
                            (id, exam, year, organizer, section, qno, stem, options_json, answer_key, pdf, source_url, key_url, provenance, sha256)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (q['id'], q['exam'], q['year'], q['organizer'], q['section'], q['qno'],
                              q['stem'], q['options_json'], q['answer_key'], q['pdf'], q['source_url'],
                              q['key_url'], q['provenance'], q['sha256']))
                        total_questions += 1
                    except sqlite3.IntegrityError:
                        pass
                
                print(f"  Extracted {len(questions)} questions")
            else:
                print(f"  No PDF found for ESE {year} {section} (expected: {pdf_name})")
    
    conn.commit()
    
    # Verify
    count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    by_year_sec = conn.execute("SELECT year, section, COUNT(*) FROM questions GROUP BY year, section ORDER BY year, section").fetchall()
    conn.close()
    
    print(f"\nDatabase built: {output_path}")
    print(f"Total questions: {count}")
    for year, section, cnt in by_year_sec:
        print(f"  {year} {section}: {cnt} questions")

def main():
    parser = argparse.ArgumentParser(description="Build official UPSC ESE PYQ database via OCR")
    parser.add_argument("--download", action="store_true", help="Download PDFs (not fully implemented for UPSC)")
    parser.add_argument("--parse-only", action="store_true", help="OCR existing PDFs in --input-dir")
    parser.add_argument("--input-dir", type=Path, help="Directory containing ESE PDFs")
    parser.add_argument("--output", type=Path, required=True, help="Output SQLite database path")
    
    args = parser.parse_args()
    
    if args.download:
        build_database(args.output, download=True)
    elif args.parse_only:
        if not args.input_dir:
            parser.error("--parse-only requires --input-dir")
        build_database(args.output, input_dir=args.input_dir)
    else:
        parser.error("Use --download or --parse-only")

if __name__ == "__main__":
    main()
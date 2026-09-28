#!/usr/bin/env python3
"""official_pyq.py - Download and parse official GATE EE question papers (2016-2026) from IIT websites.

Creates a SQLite database with provenance=official_pyq.
Source PDFs: gate2026.iitg.ac.in, gate2025.iitr.ac.in, gate2027.iitm.ac.in (official IIT sites only).

Usage:
    python3 scripts/official_pyq.py --download --parse --output ~/data/gate_official_pyq.sqlite
    python3 scripts/official_pyq.py --parse-only --input-dir ~/AIR10_LIBRARY/official_pyq --output ~/data/gate_official_pyq.sqlite
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
from urllib.parse import urljoin

try:
    import fitz  # PyMuPDF
except ImportError:
    print("PyMuPDF (fitz) required: pip install pymupdf")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("requests required: pip install requests")
    sys.exit(1)

# Official GATE EE PDF URLs (2016-2026) - from organizing IIT sites only
GATE_EE_URLS = {
    2026: "https://gate2026.iitg.ac.in/doc/download/2026/QPs/EE.pdf",
    2025: "https://gate2025.iitr.ac.in/doc/2025/2025_QP/EE.pdf",
    2024: "https://gate2027.iitm.ac.in/static/doc/download/2024/EE24S8.pdf",
    2023: "https://gate2027.iitm.ac.in/static/doc/download/2023/ee_2023.pdf",
    2022: "https://gate2027.iitm.ac.in/static/doc/download/2022/ee_2022.pdf",
    2021: "https://gate2027.iitm.ac.in/static/doc/download/2021/ee_2021.pdf",
    2020: "https://gate2026.iitg.ac.in/doc/download/2020/ee_2020.pdf",
    2019: "https://gate2026.iitg.ac.in/doc/download/2019/ee_2019.pdf",
    # 2016-2018: Google Drive links from IIT (same file for all 3 years in some cases)
    2018: "https://drive.google.com/file/d/15_ICpSsDqPOvTxa8irh-13zRM9paY-SY/view",
    2017: "https://drive.google.com/file/d/15_ICpSsDqPOvTxa8irh-13zRM9paY-SY/view",
    2016: "https://drive.google.com/file/d/15_ICpSsDqPOvTxa8irh-13zRM9paY-SY/view",
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id TEXT PRIMARY KEY,
    exam TEXT NOT NULL,
    year INTEGER NOT NULL,
    organizer TEXT NOT NULL,
    section TEXT NOT NULL,
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

def download_pdf(url: str, dest: Path) -> bool:
    """Download a PDF from URL. Returns True on success."""
    try:
        # Handle Google Drive links
        if "drive.google.com" in url:
            file_id = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
            if file_id:
                url = f"https://drive.google.com/uc?export=download&id={file_id.group(1)}"
        
        headers = {"User-Agent": "awesome-electrical-exams/1.0 (+https://github.com/lakhidas168-ship-it)"}
        resp = requests.get(url, headers=headers, timeout=60, stream=True)
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

def extract_questions_from_pdf(pdf_path: Path, year: int, source_url: str) -> list:
    """Extract questions from a GATE EE PDF. Returns list of dicts."""
    questions = []
    doc = fitz.open(pdf_path)
    
    # GATE papers typically have: question number, stem, 4 options, answer key at end
    # This is a simplified extractor - real parsing needs per-year tuning
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()
    
    # Pattern for GATE questions: Q.1, Q.2, etc. with options (A), (B), (C), (D)
    # This is a basic pattern - real implementation needs more sophistication
    q_pattern = re.compile(
        r'Q\.?\s*(\d+)[\.\s]+(.+?)(?:\n\s*\(A\)\s*(.+?))?'
        r'(?:\n\s*\(B\)\s*(.+?))?(?:\n\s*\(C\)\s*(.+?))?(?:\n\s*\(D\)\s*(.+?))?',
        re.DOTALL | re.MULTILINE
    )
    
    for match in q_pattern.finditer(full_text):
        qno = match.group(1)
        stem = match.group(2).strip() if match.group(2) else ""
        opts = {
            'a': match.group(3).strip() if match.group(3) else "",
            'b': match.group(4).strip() if match.group(4) else "",
            'c': match.group(5).strip() if match.group(5) else "",
            'd': match.group(6).strip() if match.group(6) else "",
        }
        
        if stem and any(opts.values()):
            questions.append({
                'id': f"GATE{year}_EE_{qno}",
                'exam': '|gate|',
                'year': year,
                'organizer': f'IIT (GATE {year})',
                'section': 'EE',
                'qno': qno,
                'stem': stem[:2000],
                'options_json': json.dumps(opts),
                'answer_key': '',  # Answer keys not always in the same PDF
                'pdf': str(pdf_path),
                'source_url': source_url,
                'key_url': '',
                'provenance': 'official_pyq',
            })
    
    return questions

def build_database(output_path: Path, input_dir: Path = None, download: bool = False):
    """Build the official GATE EE PYQ database."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(output_path)
    conn.executescript(SCHEMA)
    
    total_questions = 0
    
    for year in range(2016, 2027):
        url = GATE_EE_URLS.get(year)
        if not url:
            print(f"No URL for GATE {year}")
            continue
        
        pdf_path = None
        if download:
            pdf_dir = input_dir or Path(tempfile.gettempdir()) / "gate_pdfs"
            pdf_dir.mkdir(parents=True, exist_ok=True)
            pdf_path = pdf_dir / f"GATE{year}_EE.pdf"
            
            if not pdf_path.exists():
                print(f"Downloading GATE {year} EE...")
                if not download_pdf(url, pdf_path):
                    continue
            else:
                print(f"Using cached: {pdf_path}")
        elif input_dir:
            # Look for existing PDF
            candidates = list(input_dir.glob(f"*{year}*EE*.pdf")) + list(input_dir.glob(f"*GATE*{year}*EE*.pdf"))
            if candidates:
                pdf_path = candidates[0]
        
        if pdf_path and pdf_path.exists():
            print(f"Parsing GATE {year} EE...")
            questions = extract_questions_from_pdf(pdf_path, year, url)
            
            for q in questions:
                q['sha256'] = sha256_file(pdf_path)
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
                    pass  # Duplicate
            
            print(f"  Extracted {len(questions)} questions")
        else:
            print(f"  No PDF found for {year}")
    
    conn.commit()
    
    # Verify
    count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    by_year = conn.execute("SELECT year, COUNT(*) FROM questions GROUP BY year ORDER BY year").fetchall()
    conn.close()
    
    print(f"\nDatabase built: {output_path}")
    print(f"Total questions: {count}")
    for year, cnt in by_year:
        print(f"  {year}: {cnt} questions")

def main():
    parser = argparse.ArgumentParser(description="Build official GATE EE PYQ database")
    parser.add_argument("--download", action="store_true", help="Download PDFs from official IIT sites")
    parser.add_argument("--parse-only", action="store_true", help="Parse existing PDFs in --input-dir")
    parser.add_argument("--input-dir", type=Path, help="Directory containing GATE EE PDFs")
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
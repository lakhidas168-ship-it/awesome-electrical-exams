#!/usr/bin/env python3
"""prerequisites.py - Dependency checks for air10-exam.

Verifies that required and optional dependencies are available.
"""
import importlib
import sys
from typing import List, Tuple

REQUIRED = [
    ("mcp", "mcp>=1.0.0"),
    ("numpy", "numpy>=1.26.0"),
    ("scipy", "scipy>=1.12.0"),
    ("sympy", "sympy>=1.12.0"),
    ("pandas", "pandas>=2.1.0"),
    ("requests", "requests>=2.31.0"),
    ("tqdm", "tqdm>=4.66.0"),
    ("dotenv", "python-dotenv>=1.0.0"),  # package is python-dotenv, import is dotenv
]

OPTIONAL_SOLVERS = [
    ("lcapy", "lcapy>=0.90.0"),
    ("control", "control>=0.9.4"),
    ("pandapower", "pandapower>=3.0.0"),
]

OPTIONAL_ML = [
    ("flashrank", "flashrank>=0.1.0"),
    ("sentence_transformers", "sentence-transformers>=2.2.0"),
]

SYSTEM_TOOLS = [
    ("tesseract", "tesseract-ocr"),
    ("pandoc", "pandoc"),
]


def check_imports(packages: List[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
    """Check if packages can be imported. Returns (available, missing)."""
    available = []
    missing = []
    for import_name, pip_name in packages:
        try:
            importlib.import_module(import_name)
            available.append(pip_name)
        except ImportError:
            missing.append(pip_name)
    return available, missing


def check_system_tools(tools: List[Tuple[str, str]]) -> Tuple[List[str], List[str]]:
    """Check if system tools are available. Returns (available, missing)."""
    import shutil
    available = []
    missing = []
    for cmd, pkg in tools:
        if shutil.which(cmd):
            available.append(pkg)
        else:
            missing.append(pkg)
    return available, missing


def main() -> int:
    print("=" * 60)
    print("air10-exam Dependency Check")
    print("=" * 60)
    
    # Required
    print("\n[REQUIRED]")
    avail, miss = check_imports(REQUIRED)
    for p in avail:
        print(f"  ✓ {p}")
    for p in miss:
        print(f"  ✗ {p} (pip install {p})")
    
    # Optional solvers
    print("\n[OPTIONAL: EE Solvers]")
    avail, miss = check_imports(OPTIONAL_SOLVERS)
    for p in avail:
        print(f"  ✓ {p}")
    for p in miss:
        print(f"  ○ {p} (pip install {p}) -- needed for netlist/control/twoport solvers")
    
    # Optional ML
    print("\n[OPTIONAL: ML/Ranking]")
    avail, miss = check_imports(OPTIONAL_ML)
    for p in avail:
        print(f"  ✓ {p}")
    for p in miss:
        print(f"  ○ {p} (pip install {p}) -- needed for FlashRank reranking")
    
    # System tools
    print("\n[SYSTEM TOOLS]")
    avail, miss = check_system_tools(SYSTEM_TOOLS)
    for p in avail:
        print(f"  ✓ {p}")
    for p in miss:
        print(f"  ○ {p} (apt/brew install {p}) -- needed for OCR/PDF processing")
    
    print("\n" + "=" * 60)
    if miss:
        print("Some REQUIRED dependencies are missing. Install with:")
        print(f"  pip install {' '.join(miss)}")
        return 1
    else:
        print("All REQUIRED dependencies satisfied!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
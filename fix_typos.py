import os
import json
import sys
from pathlib import Path

def fix_typos(obj):
    """Recursively fix typos in inferred-type values."""
    found_any = False
    if isinstance(obj, dict):
        if "inferred-type" in obj:
            if obj["inferred-type"] == "unkown":
                obj["inferred-type"] = "unknown"
                found_any = True
            elif obj["inferred-type"] == "advertisment":
                obj["inferred-type"] = "advertisement"
                found_any = True
        for key in obj:
            if fix_typos(obj[key]):
                found_any = True
    elif isinstance(obj, list):
        for item in obj:
            if fix_typos(item):
                found_any = True
    return found_any

def process_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if fix_typos(data):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_typos.py <dir1> [dir2 ...]")
        sys.exit(1)
    
    total_scanned = 0
    total_fixed = 0
    
    for root_dir in sys.argv[1:]:
        print(f"--- Starting Scan: {root_dir} ---")
        path_obj = Path(root_dir)
        if not path_obj.exists():
            print(f"Directory {root_dir} does not exist, skipping.")
            continue
            
        for path in path_obj.rglob("*.json"):
            total_scanned += 1
            if process_file(path):
                total_fixed += 1
                print(f"Fixed: {path}")
    
    print("\n" + "="*40)
    print("FINISHED TYPO CORRECTION")
    print(f"Total JSON files scanned: {total_scanned}")
    print(f"Total files corrected:    {total_fixed}")
    print("="*40)
    if total_fixed == 0:
        print("No typos were found. Your data is already clean!")
    else:
        print("All found typos have been corrected.")

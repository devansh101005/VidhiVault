import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.parser import parse_pdf
import json

result = parse_pdf("tests/sample_clean.PDF")

print(f"Pages: {len(result['pages'])}")
print(f"Metadata: {json.dumps(result['metadata'], indent=2, default=str)}")
print()

for i, page in enumerate(result["pages"]):
    text = page["text"].strip()
    print(f"=== Page {i+1} ({len(text)} chars) ===")
    print(text[:800])
    print()

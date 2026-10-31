"""Print the number of usable local evidence documents; does not call external services."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.rag.local_corpus import corpus_status
print(corpus_status())

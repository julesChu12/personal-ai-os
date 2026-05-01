from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.memory.embedding_provider import build_embedding_provider, validate_embedding_dimension


def main() -> None:
    provider = build_embedding_provider()
    vector = provider.embed_texts(["personal-ai-os embedding smoke"])[0]
    validate_embedding_dimension(vector, settings.embedding_dimension)
    print("embedding provider check passed")


if __name__ == "__main__":
    main()

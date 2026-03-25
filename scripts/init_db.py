#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

load_dotenv(src_dir / 'fse_memory' / '.env')

# .env sets POSTGRES_HOST=postgres (Docker service name); override for local runs
if os.environ.get('POSTGRES_HOST') == 'postgres':
    os.environ['POSTGRES_HOST'] = 'localhost'

from fse_memory.fse_profile import init_fse_schema
from core_rag.memory.db import init_db as init_core_rag_db


def main():
    print("Initializing PantherBot database...")

    try:
        init_core_rag_db()
        print("Core_RAG tables created:")
        print("  - sessions")
        print("  - messages")
        print("  - archived_messages")
        print("  - compressions")

        init_fse_schema()
        print("\nFSE tables created:")
        print("  - student_profiles")
        print("  - citations")

        print("\nDatabase initialized successfully")

    except Exception as e:
        print(f"Error initializing database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

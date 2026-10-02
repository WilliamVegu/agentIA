#!/usr/bin/env python3
"""
Seed script for populating studio.db with representative historical AgentIA generation sessions.
"""

import sys
from pathlib import Path

# Add project root and backend to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
backend_dir = repo_root / "backend"
for p in (repo_root, backend_dir):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from tests.fixtures.baseline_fixture_db import create_fixture_database
except ImportError:
    from backend.tests.fixtures.baseline_fixture_db import create_fixture_database


def main():
    target_db = Path("backend/studio.db")
    if len(sys.argv) > 1:
        target_db = Path(sys.argv[1])

    print(f"[INFO] Populating {target_db} with representative historical session data...")
    create_fixture_database(target_db, session_count=50)
    print(f"[SUCCESS] Successfully seeded {target_db} with 50 historical generation sessions.")


if __name__ == "__main__":
    main()

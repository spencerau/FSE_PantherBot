import os
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

FSE_COLLECTIONS = {"major_catalogs", "minor_catalogs", "4_year_plans", "general_knowledge"}


@pytest.fixture(scope="session", autouse=True)
def set_test_env():
    os.environ.setdefault("QDRANT_HOST", "localhost")
    os.environ.setdefault("POSTGRES_HOST", "localhost")
    os.environ.setdefault("POSTGRES_PORT", "5432")
    os.environ.setdefault("POSTGRES_DB", "pantherbot")
    os.environ.setdefault("POSTGRES_USER", "pantherbot")
    os.environ.setdefault("POSTGRES_PASSWORD", "pantherbot_secure_2025")


@pytest.fixture(scope="module")
def rag():
    from fse_retrieval.fse_unified_rag import FSEUnifiedRAG
    return FSEUnifiedRAG()


@pytest.fixture(autouse=True)
def assert_no_routing_error(request):
    yield
    # Nothing to inspect post-test; validation happens inside test_query.py via debug_info.
    # This hook exists as a placeholder for future router output capture.

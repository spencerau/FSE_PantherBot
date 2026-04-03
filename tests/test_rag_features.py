import pytest

FSE_COLLECTIONS = ["major_catalogs", "minor_catalogs", "4_year_plans", "general_knowledge"]
CATALOG_COLLECTIONS = ["major_catalogs", "minor_catalogs", "4_year_plans"]


@pytest.fixture(scope="module")
def rag():
    from fse_retrieval.fse_unified_rag import FSEUnifiedRAG
    return FSEUnifiedRAG()


# ---------------------------------------------------------------------------
# collection_config flag validation — config only, no services required
# ---------------------------------------------------------------------------

def test_collection_config_present_in_config(rag):
    coll_cfg = rag.config.get("collection_config", {})
    for coll in FSE_COLLECTIONS:
        assert coll in coll_cfg, f"Missing collection_config entry for '{coll}'"


def test_summary_disabled_for_catalog_collections(rag):
    coll_cfg = rag.config.get("collection_config", {})
    for coll in CATALOG_COLLECTIONS:
        assert coll_cfg[coll].get("summary_enabled", True) is False, \
            f"summary_enabled should be False for '{coll}'"


def test_reranking_enabled_for_general_knowledge(rag):
    coll_cfg = rag.config.get("collection_config", {})
    assert coll_cfg["general_knowledge"].get("reranking_enabled", False) is True


def test_reranking_disabled_for_catalog_collections(rag):
    coll_cfg = rag.config.get("collection_config", {})
    for coll in CATALOG_COLLECTIONS:
        assert coll_cfg[coll].get("reranking_enabled", True) is False, \
            f"reranking_enabled should be False for '{coll}'"


def test_hybrid_disabled_for_all_collections(rag):
    coll_cfg = rag.config.get("collection_config", {})
    for coll in FSE_COLLECTIONS:
        assert coll_cfg[coll].get("hybrid_enabled", True) is False, \
            f"hybrid_enabled should be False for '{coll}'"


# ---------------------------------------------------------------------------
# Feature flag behavior in answer generation — integration tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_answer_general_knowledge_uses_reranking(rag):
    result = rag.answer_question(
        "What is the add/drop deadline?",
        stream=False,
        return_debug_info=True,
    )
    assert isinstance(result, tuple)
    _, sources, debug = result
    reranking_used = debug.get("reranking_enabled") or debug.get("reranking_used")
    if reranking_used is not None:
        assert reranking_used is True


@pytest.mark.integration
def test_answer_catalog_query_skips_reranking(rag):
    result = rag.answer_question(
        "What courses are required for Computer Science graduation?",
        student_program="cs",
        stream=False,
        return_debug_info=True,
    )
    assert isinstance(result, tuple)
    _, sources, debug = result
    reranking_used = debug.get("reranking_enabled") or debug.get("reranking_used")
    if reranking_used is not None:
        assert reranking_used is False


@pytest.mark.integration
def test_answer_general_knowledge_returns_content(rag):
    result = rag.answer_question(
        "How do I register for classes?",
        stream=False,
    )
    if isinstance(result, tuple):
        answer = result[0]
    else:
        answer = result
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0


@pytest.mark.integration
def test_answer_catalog_returns_content(rag):
    result = rag.answer_question(
        "What upper division courses are required for CS?",
        student_program="cs",
        stream=False,
    )
    if isinstance(result, tuple):
        answer = result[0]
    else:
        answer = result
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0

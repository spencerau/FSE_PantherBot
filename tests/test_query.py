import pytest
from typing import List, Dict

FSE_COLLECTIONS = {"major_catalogs", "minor_catalogs", "4_year_plans", "general_knowledge"}

ROUTING_CASES = [
    ("What courses do I need to graduate with a CS degree?", ["major_catalogs"]),
    ("What are the analytics minor requirements?", ["minor_catalogs"]),
    ("Generate a 4 year plan for CS major and game dev minor", ["4_year_plans", "major_catalogs", "minor_catalogs"]),
    ("When should I take CPSC 350?", ["4_year_plans", "major_catalogs"]),
    ("What is the add/drop deadline?", ["general_knowledge"]),
]


@pytest.fixture(scope="module")
def rag():
    from fse_retrieval.fse_unified_rag import FSEUnifiedRAG
    return FSEUnifiedRAG()


@pytest.fixture
def user_context():
    return {"program": "cs", "year": "2024"}


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_rag_initialization(rag):
    assert rag.config is not None
    assert rag.client is not None
    assert rag.llm_handler is not None
    assert rag.answer_gen is not None


@pytest.mark.integration
def test_query_router_initialized(rag):
    assert rag.query_router is not None


# ---------------------------------------------------------------------------
# search_collection — per collection
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_search_collection_major_catalogs(rag, user_context):
    results = rag.search_collection("graduation requirements", "major_catalogs", user_context, top_k=5)
    assert len(results) >= 1
    for r in results:
        assert "text" in r
        assert r["collection"] == "major_catalogs"


@pytest.mark.integration
def test_search_collection_minor_catalogs(rag):
    results = rag.search_collection("minor requirements analytics", "minor_catalogs", None, top_k=5)
    assert len(results) >= 1
    for r in results:
        assert r["collection"] == "minor_catalogs"


@pytest.mark.integration
def test_search_collection_4_year_plans(rag, user_context):
    results = rag.search_collection("freshman year courses", "4_year_plans", user_context, top_k=5)
    assert len(results) >= 1
    for r in results:
        assert r["collection"] == "4_year_plans"


@pytest.mark.integration
def test_search_collection_general_knowledge(rag):
    results = rag.search_collection("add/drop deadline registration", "general_knowledge", None, top_k=5)
    assert len(results) >= 1
    for r in results:
        assert r["collection"] == "general_knowledge"


# ---------------------------------------------------------------------------
# Metadata filter correctness
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_metadata_filter_subject_code(rag):
    ctx = {"program": "cs"}
    results = rag.search_collection("courses required", "major_catalogs", ctx, top_k=10)
    subject_codes = {r["metadata"].get("SubjectCode") for r in results if r.get("metadata")}
    assert "cs" in subject_codes or not subject_codes - {None}


@pytest.mark.integration
def test_metadata_filter_year(rag):
    ctx = {"year": "2024"}
    results = rag.search_collection("graduation requirements", "major_catalogs", ctx, top_k=10)
    years = {r["metadata"].get("Year") for r in results if r.get("metadata")}
    assert "2024" in years or not years - {None}


# ---------------------------------------------------------------------------
# Query routing
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("query,expected_collections", ROUTING_CASES)
def test_query_router_returns_valid_collections(rag, query, expected_collections):
    result = rag.query_router.route_query(query, {})
    returned = result['collections']
    assert isinstance(returned, list)
    assert all(c in FSE_COLLECTIONS for c in returned), f"Unknown collection in: {returned}"
    for expected in expected_collections:
        assert expected in returned, (
            f"Expected '{expected}' in routing result for query: '{query}'\nGot: {returned}"
        )


@pytest.mark.integration
def test_query_router_structured_output(rag):
    result = rag.query_router.route_query("What electives can I take for CS?", {})
    assert isinstance(result['collections'], list)
    assert len(result['collections']) >= 1
    assert 200 <= result['token_allocation'] <= 15000


@pytest.mark.integration
def test_four_year_plan_routing_includes_all_collections(rag):
    result = rag.query_router.route_query(
        "Generate a 4 year plan for CS major and game dev minor", {}
    )
    assert "4_year_plans" in result['collections']
    assert "major_catalogs" in result['collections']
    assert "minor_catalogs" in result['collections']


# ---------------------------------------------------------------------------
# Answer generation
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_answer_question_basic(rag):
    result = rag.answer_question(
        "What math courses are required for Computer Science?",
        student_program="cs",
        student_year="2024",
        stream=False,
    )
    if isinstance(result, tuple):
        answer = result[0]
    else:
        answer = result
    assert isinstance(answer, str)
    assert len(answer.strip()) > 0


@pytest.mark.integration
def test_answer_question_returns_debug_info(rag):
    result = rag.answer_question(
        "What are the CPSC 350 prerequisites?",
        student_program="cs",
        stream=False,
        return_debug_info=True,
    )
    assert isinstance(result, tuple)
    _, sources, debug = result
    assert "collections_searched" in debug or isinstance(sources, list)


@pytest.mark.integration
def test_answer_question_streaming(rag):
    tokens = list(rag.answer_question(
        "What courses are required for graduation?",
        student_program="cs",
        stream=True,
    ))
    assert len(tokens) > 0
    assert any(isinstance(t, str) and t for t in tokens)


@pytest.mark.integration
def test_answer_with_conversation_history(rag):
    history = [{"role": "user", "content": "What major are we discussing?"}]
    result = rag.answer_question(
        "What are the requirements?",
        student_program="cs",
        conversation_history=history,
        stream=False,
    )
    if isinstance(result, tuple):
        answer = result[0]
    else:
        answer = result
    assert isinstance(answer, str)

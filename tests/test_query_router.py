"""
Tests for the query router to ensure queries are routed to the correct collections.
Run with: PYTHONPATH=src CONFIG_FILE=config.local.yaml pytest tests/test_query_router.py -v
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

os.environ['CONFIG_FILE'] = 'config.local.yaml'

from retrieval.fse_unified_rag import FSEUnifiedRAG


@pytest.fixture(scope="module")
def rag_system():
    """Initialize RAG system once for all tests."""
    return FSEUnifiedRAG()


@pytest.fixture(scope="module")
def user_context():
    """Default user context for tests."""
    return {'program': 'compsci', 'year': '2025'}


class TestMajorCatalogsRouting:
    """Tests for queries that should route to major_catalogs only."""
    
    @pytest.mark.parametrize("query,expected", [
        ("What electives can I take for my major?", ["major_catalogs"]),
        ("What are the CS major requirements?", ["major_catalogs"]),
        ("What courses do I need to graduate?", ["major_catalogs"]),
        ("What are the prerequisites for CPSC 350?", ["major_catalogs"]),
        ("How many units do I need for my major?", ["major_catalogs"]),
        ("What upper division courses are required?", ["major_catalogs"]),
        ("Can I take CPSC 490 as an elective?", ["major_catalogs"]),
        ("What technical electives count toward my degree?", ["major_catalogs"]),
    ])
    def test_major_queries(self, rag_system, user_context, query, expected):
        result = rag_system.query_router.route_query(query, user_context=user_context)
        collections = result.get('collections', [])
        assert collections == expected, f"Query: '{query}'\nExpected: {expected}\nGot: {collections}"


class TestMinorCatalogsRouting:
    """Tests for queries that should route to minor_catalogs only."""
    
    @pytest.mark.parametrize("query,expected", [
        ("What are the analytics minor requirements?", ["minor_catalogs"]),
        ("How do I declare a minor?", ["minor_catalogs"]),
        ("What courses are in the game development minor?", ["minor_catalogs"]),
        ("Can I add a computer science minor?", ["minor_catalogs"]),
        ("What minors are available in FSE?", ["minor_catalogs"]),
    ])
    def test_minor_queries(self, rag_system, user_context, query, expected):
        result = rag_system.query_router.route_query(query, user_context=user_context)
        collections = result.get('collections', [])
        assert collections == expected, f"Query: '{query}'\nExpected: {expected}\nGot: {collections}"


class TestFourYearPlansRouting:
    """Tests for queries that should route to 4_year_plans + major_catalogs."""
    
    @pytest.mark.parametrize("query,expected", [
        ("When should I take CPSC 406?", ["4_year_plans", "major_catalogs"]),
        ("What semester should I take CPSC 350?", ["4_year_plans", "major_catalogs"]),
        ("What classes should I take freshman year?", ["4_year_plans", "major_catalogs"]),
        ("What courses should I take in my third year?", ["4_year_plans", "major_catalogs"]),
        ("What is the recommended course sequence?", ["4_year_plans", "major_catalogs"]),
        ("Should I take CPSC 230 before CPSC 231?", ["4_year_plans", "major_catalogs"]),
    ])
    def test_scheduling_queries(self, rag_system, user_context, query, expected):
        result = rag_system.query_router.route_query(query, user_context=user_context)
        collections = result.get('collections', [])
        # Check both collections are present (order may vary)
        assert set(collections) == set(expected), f"Query: '{query}'\nExpected: {expected}\nGot: {collections}"


class TestGeneralKnowledgeRouting:
    """Tests for queries that should route to general_knowledge only."""
    
    @pytest.mark.parametrize("query,expected", [
        ("What is the registration deadline?", ["general_knowledge"]),
        ("When is the add/drop deadline?", ["general_knowledge"]),
        ("How do I register for classes?", ["general_knowledge"]),
        ("How do I get a permission number?", ["general_knowledge"]),
        ("What are the themed inquiry requirements?", ["general_knowledge"]),
        ("What is the academic probation policy?", ["general_knowledge"]),
    ])
    def test_policy_queries(self, rag_system, user_context, query, expected):
        result = rag_system.query_router.route_query(query, user_context=user_context)
        collections = result.get('collections', [])
        assert collections == expected, f"Query: '{query}'\nExpected: {expected}\nGot: {collections}"


class TestRouterConstraints:
    """Tests to ensure router doesn't over-route to too many collections."""
    
    @pytest.mark.parametrize("query", [
        "What electives can I take?",
        "What are my requirements?",
        "Help me plan my schedule",
        "What courses should I take?",
    ])
    def test_router_limits_collections(self, rag_system, user_context, query):
        result = rag_system.query_router.route_query(query, user_context=user_context)
        collections = result.get('collections', [])
        assert len(collections) <= 2, f"Router returned too many collections ({len(collections)}) for: {query}\nGot: {collections}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

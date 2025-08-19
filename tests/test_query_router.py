import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from retrieval.unified_rag import UnifiedRAG
from retrieval.query_router import QueryRouter
from utils.ollama_api import get_ollama_api


@pytest.fixture
def rag_system():
    """Create a UnifiedRAG system for testing."""
    return UnifiedRAG()


@pytest.fixture 
def query_router():
    """Create a QueryRouter for testing."""
    try:
        ollama_api = get_ollama_api()
        return QueryRouter(ollama_api)
    except Exception as e:
        pytest.skip(f"Could not initialize query router: {e}")


class TestQueryRouter:
    """Test the query routing functionality."""
    
    def test_router_initialization(self, query_router):
        """Test that the router initializes correctly."""
        assert query_router is not None
        assert hasattr(query_router, 'route_query')
        assert hasattr(query_router, 'collection_patterns')
    
    @pytest.mark.parametrize("query,expected_collections,program,year", [
        (
            "What are the CS major requirements?",
            ["major_catalogs"],
            "cs",
            "2024"
        ),
        (
            "What courses should I take freshman year?",
            ["4_year_plans"],  # Should include 4_year_plans
            "cs", 
            "2024"
        ),
        (
            "Analytics minor requirements",
            ["minor_catalogs"],
            None,
            None
        ),
        (
            "When is registration deadline?",
            ["general_knowledge"],
            None,
            None
        ),
        (
            "How do I book an appointment with an academic advisor?",
            ["general_knowledge"],
            "Computer Science",  # Should NOT include major_catalogs even with program
            "2024"
        ),
        (
            "Computer Science degree requirements and freshman year schedule",
            ["major_catalogs", "4_year_plans"],
            "cs",
            "2024"
        )
    ])
    def test_query_routing_cases(self, query_router, query, expected_collections, program, year):
        """Test specific query routing cases."""
        collections = query_router.route_query(query, program, year, method='hybrid')
        
        # Check that at least one expected collection is present
        found_expected = any(expected in collections for expected in expected_collections)
        assert found_expected, f"Expected one of {expected_collections} but got {collections}"
    
    def test_routing_methods(self, query_router):
        """Test different routing methods."""
        query = "What are the graduation requirements?"
        
        methods = ['keyword', 'hybrid']
        if query_router.semantic_enabled:
            methods.append('semantic')
        
        for method in methods:
            collections = query_router.route_query(query, "cs", "2024", method=method)
            assert isinstance(collections, list)
            assert len(collections) > 0
    
    def test_contextual_collection_logic(self, query_router):
        """Test that contextual collection addition works correctly."""
        # Query that should NOT add major_catalogs even with student_program
        advisor_query = "How do I book an appointment with an academic advisor?"
        collections = query_router.route_query(advisor_query, "Computer Science", "2024", method='hybrid')
        
        # Should be general_knowledge only, NOT major_catalogs
        assert "general_knowledge" in collections
        assert "major_catalogs" not in collections
        
        # Query that SHOULD add major_catalogs with student_program
        requirements_query = "What are the graduation requirements?"
        collections2 = query_router.route_query(requirements_query, "Computer Science", "2024", method='hybrid')
        
        # Should include major_catalogs for academic requirements
        assert "major_catalogs" in collections2


class TestDynamicChunkAllocation:
    """Test the dynamic chunk allocation system."""
    
    def test_chunk_allocation_calculation(self, rag_system):
        """Test dynamic chunk allocation calculation."""
        collections = ["major_catalogs", "general_knowledge"]
        query = "CS requirements and registration info"
        
        allocation = rag_system._calculate_dynamic_chunk_allocation(collections, query)
        
        assert isinstance(allocation, dict)
        assert len(allocation) > 0
        
        # Check that total allocation is reasonable
        total_chunks = sum(allocation.values())
        assert total_chunks > 0
        assert total_chunks <= rag_system.config['retrieval']['total_retrieval_budget']
    
    def test_single_collection_allocation(self, rag_system):
        """Test allocation for single collection."""
        collections = ["general_knowledge"]
        query = "Registration deadline"
        
        allocation = rag_system._calculate_dynamic_chunk_allocation(collections, query)
        
        assert "general_knowledge" in allocation
        assert allocation["general_knowledge"] >= rag_system.config['retrieval']['min_chunks_per_collection']
    
    def test_multi_collection_allocation(self, rag_system):
        """Test allocation for multiple collections."""
        collections = ["major_catalogs", "4_year_plans", "general_knowledge"]
        query = "CS major requirements, course sequence, and registration"
        
        allocation = rag_system._calculate_dynamic_chunk_allocation(collections, query)
        
        # All collections should get some chunks
        for collection in collections:
            assert collection in allocation
            assert allocation[collection] > 0


class TestMultiCollectionSearch:
    """Test the multi-collection search functionality."""
    
    def test_general_knowledge_search_without_filters(self, rag_system):
        """Test that general_knowledge searches work without student program filters."""
        query = "How do I book an appointment with an academic advisor?"
        
        # Search general_knowledge directly
        results = rag_system.search_collection(
            query, 
            "general_knowledge", 
            student_program=None,  # No filters
            student_year=None,
            top_k=10
        )
        
        assert len(results) > 0
        
        # Check if advisor booking info is found
        found_advisor = False
        for result in results:
            if "academic advising appointment booking" in result.get('text', '').lower():
                found_advisor = True
                break
        
        assert found_advisor, "Academic advisor booking information should be found"
    
    def test_search_multiple_collections_integration(self, rag_system):
        """Test the full search_multiple_collections method."""
        query = "How do I book an appointment with an academic advisor?"
        collections_to_search = ["general_knowledge"]
        
        results = rag_system.search_multiple_collections(
            query,
            collections_to_search,
            student_program="Computer Science",  # This should NOT filter general_knowledge
            student_year="2024",
            top_k_per_collection=10
        )
        
        assert len(results) > 0
        
        # Verify results are from general_knowledge
        for result in results:
            assert result.get('collection') == 'general_knowledge'
    
    def test_major_catalogs_with_filters(self, rag_system):
        """Test that major_catalogs correctly applies student program filters."""
        query = "What are the graduation requirements?"
        collections_to_search = ["major_catalogs"]
        
        results = rag_system.search_multiple_collections(
            query,
            collections_to_search,
            student_program="Computer Science",
            student_year="2024",
            top_k_per_collection=10
        )
        
        assert len(results) > 0
        
        # Verify results are from major_catalogs
        for result in results[:5]:  # Check first 5
            assert result.get('collection') == 'major_catalogs'


class TestFullPipeline:
    """Test the complete RAG pipeline with the new routing system."""
    
    @pytest.mark.parametrize("query,program,year,expected_collections", [
        (
            "How do I book an appointment with an academic advisor?",
            "Computer Science",
            "2024", 
            ["general_knowledge"]
        ),
        (
            "What are the Computer Science major requirements?",
            "Computer Science",
            "2024",
            ["major_catalogs"]
        ),
        (
            "What courses should I take freshman year in CS?",
            "Computer Science", 
            "2024",
            ["major_catalogs", "4_year_plans"]  # Could be either/both
        )
    ])
    def test_end_to_end_pipeline(self, rag_system, query, program, year, expected_collections):
        """Test the complete pipeline from query to results."""
        
        answer, chunks = rag_system.answer_question(
            query,
            student_program=program,
            student_year=year,
            top_k=15,
            use_streaming=False,
            test_mode=True  # Skip LLM generation for testing
        )
        
        assert len(chunks) > 0, f"No chunks retrieved for query: {query}"
        
        # Check collection distribution
        collections_found = set()
        for chunk in chunks:
            collections_found.add(chunk.get('collection', 'unknown'))
        
        # At least one expected collection should be present
        found_expected = any(expected in collections_found for expected in expected_collections)
        assert found_expected, f"Expected collections {expected_collections}, but got {list(collections_found)}"
    
    def test_advisor_booking_retrieval(self, rag_system):
        """Specific test for academic advisor booking retrieval."""
        query = "How do I book an appointment with an academic advisor?"
        
        answer, chunks = rag_system.answer_question(
            query,
            student_program="Computer Science",
            student_year="2024",
            test_mode=True
        )
        
        # Should find the academic advisor booking information
        found_booking = False
        for chunk in chunks:
            text = chunk.get('text', '').lower()
            if 'academic advising appointment booking' in text:
                found_booking = True
                # Should be from general_knowledge
                assert chunk.get('collection') == 'general_knowledge'
                break
        
        assert found_booking, "Academic advisor booking information should be retrieved"
    
    def test_routing_consistency(self, rag_system):
        """Test that routing is consistent with search results."""
        if not rag_system.query_router:
            pytest.skip("Query router not available")
        
        query = "How do I book an appointment with an academic advisor?"
        
        # Get router decision
        router_collections = rag_system.query_router.route_query(
            query, "Computer Science", "2024", method='hybrid'
        )
        
        # Get actual search results  
        answer, chunks = rag_system.answer_question(
            query,
            student_program="Computer Science",
            student_year="2024",
            test_mode=True
        )
        
        # Verify chunks come from routed collections
        result_collections = set(chunk.get('collection') for chunk in chunks)
        
        # Should have overlap between router decision and actual results
        overlap = set(router_collections) & result_collections
        assert len(overlap) > 0, f"Router selected {router_collections} but got results from {result_collections}"

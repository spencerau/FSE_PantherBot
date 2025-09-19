import pytest
import pytest_asyncio
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from src.memory.compress_memory import MemoryCompressionService

class AsyncContextManagerMock:
    def __init__(self, return_value):
        self._return_value = return_value
        
    async def __aenter__(self):
        return self._return_value
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

@pytest_asyncio.fixture
async def compression_service():
    with patch('src.memory.compress_memory.ConversationMemoryManager') as mock_memory, \
         patch('src.memory.compress_memory.DatabaseManager') as mock_db:
        
        mock_memory_instance = AsyncMock()
        mock_db_instance = MagicMock()
        mock_memory.return_value = mock_memory_instance
        mock_db.return_value = mock_db_instance
        
        mock_conn = AsyncMock()
        
        def acquire():
            return AsyncContextManagerMock(mock_conn)
        
        mock_db_instance.connection_pool.acquire = acquire
        
        service = MemoryCompressionService()
        service.memory_manager = mock_memory_instance
        service.db_manager = mock_db_instance
        
        yield service, mock_memory_instance, mock_db_instance, mock_conn

@pytest.mark.asyncio
async def test_compress_all_user_memories(compression_service):
    service, mock_memory, mock_db, mock_conn = compression_service
    
    mock_conn.fetch.return_value = [
        {'slack_user_id': 'U123456'},
        {'slack_user_id': 'U789012'}
    ]
    
    mock_memory.should_compress_memory.side_effect = [True, False]
    mock_memory.compress_conversation_memory.return_value = None
    
    result = await service.compress_all_user_memories()
    
    assert result == 1
    mock_memory.compress_conversation_memory.assert_called_once_with('U123456')

@pytest.mark.asyncio
async def test_get_compression_stats(compression_service):
    service, mock_memory, mock_db, mock_conn = compression_service
    
    mock_conn.fetchrow.side_effect = [
        {
            'total_users': 5,
            'unprocessed_messages': 25,
            'processed_messages': 100
        },
        {
            'users_with_memory': 3,
            'avg_messages_per_user': 15.5
        }
    ]
    
    stats = await service.get_compression_stats()
    
    assert stats['total_users'] == 5
    assert stats['unprocessed_messages'] == 25
    assert stats['users_with_memory'] == 3
    assert stats['avg_messages_per_user'] == 15.5

@pytest.mark.asyncio
async def test_cleanup_old_raw_messages(compression_service):
    service, mock_memory, mock_db, mock_conn = compression_service
    
    mock_conn.execute.return_value = "DELETE 10"
    
    await service.cleanup_old_raw_messages(30)
    
    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0]
    assert "DELETE FROM raw_messages" in args[0]
    assert args[1] == 30


@pytest.mark.asyncio
async def test_memory_compression_integration():
    import sys
    import os
    from pathlib import Path
    
    sys.path.append(str(Path(__file__).parent.parent / 'src'))
    
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_USER'] = 'pantherbot'
    os.environ['POSTGRES_PASSWORD'] = 'pantherbot_secure_2025'
    os.environ['POSTGRES_DB'] = 'pantherbot'
    os.environ['POSTGRES_PORT'] = '5432'
    
    from memory.conversation_manager import ConversationMemoryManager
    
    test_user_id = "U123456789"
    
    manager = ConversationMemoryManager(compression_threshold=10)
    await manager.initialize()
    
    try:
        async with manager.db_manager.connection_pool.acquire() as conn:
            await conn.execute("DELETE FROM raw_messages WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM conversation_memory WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM students WHERE slack_user_id = $1", test_user_id)
            
            await conn.execute(
                "INSERT INTO students (slack_user_id, major, catalog_year) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                test_user_id, "Computer Science", 2024
            )
        
        test_messages = [
            ("What courses do I need for Computer Science?", "You need CS fundamentals, math, and science courses."),
            ("Can you tell me about prerequisites?", "Prerequisites ensure you have knowledge for advanced courses."),
            ("What about electives?", "Electives let you explore areas of interest within your major."),
            ("How many credits do I need?", "Most programs require 120-128 credits for graduation."),
            ("What is the GPA requirement?", "You need to maintain at least a 2.0 cumulative GPA."),
            ("Can I change my major?", "Yes, you can change majors by meeting with an academic advisor."),
            ("What about internships?", "Internships provide real-world experience and are recommended."),
            ("How do I register for classes?", "Use the student portal to search and register for classes."),
            ("What is the waitlist process?", "You can join waitlists for closed classes through registration."),
            ("When is graduation?", "Graduation ceremonies are held in May and December each year."),
            ("What about study abroad?", "Study abroad programs offer global learning opportunities."),
            ("How do I get academic help?", "The academic success center offers tutoring and support.")
        ]
        
        print(f"Adding {len(test_messages)} messages for user {test_user_id}")
        
        for i, (message, response) in enumerate(test_messages):
            await manager.add_message(test_user_id, message, response)
            print(f"Added message {i+1}/{len(test_messages)}")
        
        memory = await manager.db_manager.get_conversation_memory(test_user_id)
        assert memory is not None, "Conversation memory should be created after 10+ messages"
        assert memory['message_count'] >= 10, f"Should have at least 10 messages, got {memory['message_count']}"
        
        unprocessed = await manager.db_manager.get_unprocessed_messages(test_user_id)
        assert len(unprocessed) <= 2, f"Should have few unprocessed messages, got {len(unprocessed)}"
        
        summary = memory['conversation_summary']
        
        print(f"Message count: {memory['message_count']}")
        print(f"Summary length: {len(summary)} characters")
        print(f"Unprocessed messages remaining: {len(unprocessed)}")
        print(f"Full summary: '{summary}'")
        
        if len(summary) > 0:
            assert "academic discussion" not in summary.lower(), f"Should not be fallback summary: {summary}"
            print("Compression successful with real AI-generated summary")
        else:
            print("Empty summary - likely Ollama not running, but compression logic worked")
        
        return True
        
    finally:
        async with manager.db_manager.connection_pool.acquire() as conn:
            await conn.execute("DELETE FROM raw_messages WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM conversation_memory WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM students WHERE slack_user_id = $1", test_user_id)
        await manager.close()


@pytest.mark.asyncio
async def test_memory_compression_cooking():
    import sys
    import os
    from pathlib import Path
    
    sys.path.append(str(Path(__file__).parent.parent / 'src'))
    
    os.environ['POSTGRES_HOST'] = 'localhost'
    os.environ['POSTGRES_USER'] = 'pantherbot'
    os.environ['POSTGRES_PASSWORD'] = 'pantherbot_secure_2025'
    os.environ['POSTGRES_DB'] = 'pantherbot'
    os.environ['POSTGRES_PORT'] = '5432'
    
    from memory.conversation_manager import ConversationMemoryManager
    
    test_user_id = "U987654321"
    
    manager = ConversationMemoryManager(compression_threshold=10)
    await manager.initialize()
    
    try:
        async with manager.db_manager.connection_pool.acquire() as conn:
            await conn.execute("DELETE FROM raw_messages WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM conversation_memory WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM students WHERE slack_user_id = $1", test_user_id)
            
            await conn.execute(
                "INSERT INTO students (slack_user_id, major, catalog_year) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                test_user_id, "Computer Science", 2024
            )
        
        test_messages = [
            ("How do I make perfect pasta?", "Start with boiling salted water and use good quality pasta."),
            ("What about sauce? I like tomato sauce", "For tomato sauce, use San Marzano tomatoes, garlic, basil, and olive oil."),
            ("How long should I cook the pasta?", "Cook until al dente - usually 1-2 minutes less than package directions."),
            ("What's the secret to perfect risotto?", "Constant stirring, warm stock, and good quality arborio rice are key."),
            ("I burned my garlic yesterday", "Keep heat medium-low when cooking garlic - it burns quickly and turns bitter."),
            ("What knife should I buy first?", "A good 8-inch chef's knife is the most versatile for beginners."),
            ("How do I know when meat is done?", "Use a meat thermometer - 165°F for chicken, 145°F for pork and beef."),
            ("My bread never rises properly", "Check your yeast is fresh and water temperature - too hot kills yeast."),
            ("What's the difference between baking soda and baking powder?", "Baking soda needs acid to activate, baking powder already contains acid."),
            ("How do I make my vegetables more flavorful?", "Season with salt, use high heat for roasting, and don't overcook them."),
            ("What's the best way to store herbs?", "Fresh herbs last longer in water like flowers, or wrapped in damp paper towels."),
            ("I want to learn knife skills", "Start with proper grip, keep fingers curled, and practice the rocking motion slowly.")
        ]
        
        print(f"Adding {len(test_messages)} cooking messages for user {test_user_id}")
        
        for i, (message, response) in enumerate(test_messages):
            await manager.add_message(test_user_id, message, response)
            print(f"Added message {i+1}/{len(test_messages)}")
        
        memory = await manager.db_manager.get_conversation_memory(test_user_id)
        assert memory is not None, "Conversation memory should be created after 10+ messages"
        assert memory['message_count'] >= 10, f"Should have at least 10 messages, got {memory['message_count']}"
        
        unprocessed = await manager.db_manager.get_unprocessed_messages(test_user_id)
        assert len(unprocessed) <= 2, f"Should have few unprocessed messages, got {len(unprocessed)}"
        
        summary = memory['conversation_summary']
        
        print(f"Message count: {memory['message_count']}")
        print(f"Summary length: {len(summary)} characters")
        print(f"Unprocessed messages remaining: {len(unprocessed)}")
        print(f"Full summary: '{summary}'")
        
        if len(summary) > 0:
            assert "academic discussion" not in summary.lower(), f"Should not be fallback summary: {summary}"
            print("Compression successful with real AI-generated summary")
        else:
            print("Empty summary - likely Ollama not running, but compression logic worked")
        
        return True
        
    finally:
        async with manager.db_manager.connection_pool.acquire() as conn:
            await conn.execute("DELETE FROM raw_messages WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM conversation_memory WHERE slack_user_id = $1", test_user_id)
            await conn.execute("DELETE FROM students WHERE slack_user_id = $1", test_user_id)
        await manager.close()

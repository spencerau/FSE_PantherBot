import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.memory.compress_memory import MemoryCompressionService

@pytest.fixture
async def compression_service():
    with patch('src.memory.compress_memory.ConversationMemoryManager') as mock_memory, \
         patch('src.memory.compress_memory.DatabaseManager') as mock_db:
        
        mock_memory_instance = AsyncMock()
        mock_db_instance = AsyncMock()
        mock_memory.return_value = mock_memory_instance
        mock_db.return_value = mock_db_instance
        
        service = MemoryCompressionService()
        service.memory_manager = mock_memory_instance
        service.db_manager = mock_db_instance
        
        yield service, mock_memory_instance, mock_db_instance

@pytest.mark.asyncio
async def test_compress_all_user_memories(compression_service):
    service, mock_memory, mock_db = compression_service
    
    mock_conn = AsyncMock()
    mock_db.connection_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_db.connection_pool.acquire.return_value.__aexit__.return_value = None
    
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
    service, mock_memory, mock_db = compression_service
    
    mock_conn = AsyncMock()
    mock_db.connection_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_db.connection_pool.acquire.return_value.__aexit__.return_value = None
    
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
    service, mock_memory, mock_db = compression_service
    
    mock_conn = AsyncMock()
    mock_db.connection_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_db.connection_pool.acquire.return_value.__aexit__.return_value = None
    
    mock_conn.execute.return_value = "DELETE 10"
    
    await service.cleanup_old_raw_messages(30)
    
    mock_conn.execute.assert_called_once()
    args = mock_conn.execute.call_args[0]
    assert "DELETE FROM raw_messages" in args[0]
    assert args[1] == 30

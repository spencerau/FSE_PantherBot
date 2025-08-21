import pytest
import pytest_asyncio
import asyncio
import os
from unittest.mock import patch, AsyncMock, MagicMock
from src.memory.database import DatabaseManager

class AsyncContextManagerMock:
    def __init__(self, mock_conn):
        self.mock_conn = mock_conn
        
    async def __aenter__(self):
        return self.mock_conn
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

@pytest_asyncio.fixture
async def db_manager():
    with patch('asyncpg.create_pool') as mock_pool:
        mock_pool_instance = MagicMock()
        mock_pool.return_value = mock_pool_instance
        
        mock_conn = AsyncMock()
        
        mock_pool_instance.acquire.return_value = AsyncContextManagerMock(mock_conn)
        
        manager = DatabaseManager()
        manager.connection_pool = mock_pool_instance
        
        yield manager, mock_conn

@pytest.mark.asyncio
async def test_database_initialization():
    with patch('asyncpg.create_pool') as mock_pool:
        mock_pool_instance = AsyncMock()
        mock_pool.return_value = mock_pool_instance
        
        manager = DatabaseManager()
        manager.connection_pool = mock_pool_instance
        
        assert manager.connection_pool is not None

@pytest.mark.asyncio
async def test_get_student_existing(db_manager):
    manager, mock_conn = db_manager
    
    mock_conn.fetchrow.return_value = {
        'slack_user_id': 'U1234567890',
        'major': 'Computer Science',
        'catalog_year': 2024
    }
    
    result = await manager.get_student('U1234567890')
    
    assert result is not None
    assert result['major'] == 'Computer Science'
    assert result['catalog_year'] == 2024

@pytest.mark.asyncio
async def test_get_student_not_found(db_manager):
    manager, mock_conn = db_manager
    
    mock_conn.fetchrow.return_value = None
    
    result = await manager.get_student('U9999999999')
    
    assert result is None

@pytest.mark.asyncio
async def test_create_student_success(db_manager):
    manager, mock_conn = db_manager
    
    mock_conn.execute.return_value = None
    
    result = await manager.create_student('U1234567890', 'Computer Science', 2024)
    
    assert result is True
    mock_conn.execute.assert_called_with(
        'INSERT INTO students (slack_user_id, major, catalog_year) VALUES ($1, $2, $3)',
        'U1234567890', 'Computer Science', 2024
    )

@pytest.mark.asyncio
async def test_create_student_failure(db_manager):
    manager, mock_conn = db_manager
    
    mock_conn.execute.side_effect = Exception("Database error")
    
    result = await manager.create_student('U1234567890', 'Computer Science', 2024)
    
    assert result is False

@pytest.mark.asyncio
async def test_add_raw_message(db_manager):
    manager, mock_conn = db_manager
    
    await manager.add_raw_message('U1234567890', 'Test message', 'Test response')
    
    mock_conn.execute.assert_called_with(
        'INSERT INTO raw_messages (slack_user_id, message_text, response_text) VALUES ($1, $2, $3)',
        'U1234567890', 'Test message', 'Test response'
    )

@pytest.mark.asyncio
async def test_get_unprocessed_messages(db_manager):
    manager, mock_conn = db_manager
    
    mock_conn.fetch.return_value = [
        {'id': 1, 'message_text': 'Test 1', 'processed': False},
        {'id': 2, 'message_text': 'Test 2', 'processed': False}
    ]
    
    result = await manager.get_unprocessed_messages('U1234567890')
    
    assert len(result) == 2
    assert result[0]['message_text'] == 'Test 1'

@pytest.mark.asyncio
async def test_update_conversation_memory_new(db_manager):
    manager, mock_conn = db_manager
    
    mock_conn.fetchrow.return_value = None
    
    await manager.update_conversation_memory('U1234567890', 'Test summary', 5)
    
    calls = mock_conn.execute.call_args_list
    assert any('INSERT INTO conversation_memory' in str(call) for call in calls)

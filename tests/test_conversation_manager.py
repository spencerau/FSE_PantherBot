import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.memory.conversation_manager import ConversationMemoryManager

@pytest.fixture
async def memory_manager():
    with patch('src.memory.conversation_manager.DatabaseManager') as mock_db, \
         patch('src.memory.conversation_manager.OllamaAPI') as mock_ollama:
        
        mock_db_instance = AsyncMock()
        mock_ollama_instance = AsyncMock()
        
        mock_db.return_value = mock_db_instance
        mock_ollama.return_value = mock_ollama_instance
        
        manager = ConversationMemoryManager(compression_threshold=3)
        manager.db_manager = mock_db_instance
        manager.ollama_api = mock_ollama_instance
        
        await manager.initialize()
        
        yield manager, mock_db_instance, mock_ollama_instance

@pytest.mark.asyncio
async def test_should_compress_memory_true(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_unprocessed_messages.return_value = [
        {'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}
    ]
    
    result = await manager.should_compress_memory('U123456')
    
    assert result is True

@pytest.mark.asyncio
async def test_should_compress_memory_false(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_unprocessed_messages.return_value = [
        {'id': 1}, {'id': 2}
    ]
    
    result = await manager.should_compress_memory('U123456')
    
    assert result is False

@pytest.mark.asyncio
async def test_format_messages_for_compression(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    messages = [
        {'message_text': 'What are the requirements?', 'response_text': 'Here are the requirements...'},
        {'message_text': 'How do I register?', 'response_text': 'To register, you need to...'}
    ]
    
    result = manager._format_messages_for_compression(messages)
    
    assert 'User: What are the requirements?' in result
    assert 'Assistant: Here are the requirements...' in result
    assert 'User: How do I register?' in result

@pytest.mark.asyncio
async def test_compress_conversation_memory(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_unprocessed_messages.return_value = [
        {'id': 1, 'message_text': 'Test 1', 'response_text': 'Response 1'},
        {'id': 2, 'message_text': 'Test 2', 'response_text': 'Response 2'},
        {'id': 3, 'message_text': 'Test 3', 'response_text': 'Response 3'}
    ]
    
    mock_db.get_conversation_memory.return_value = {
        'conversation_summary': 'Previous context',
        'message_count': 5
    }
    
    mock_ollama.generate_response.return_value = 'Compressed summary of conversation'
    
    await manager.compress_conversation_memory('U123456')
    
    mock_db.update_conversation_memory.assert_called_once_with(
        'U123456',
        'Compressed summary of conversation',
        8
    )
    
    mock_db.mark_messages_processed.assert_called_once_with([1, 2, 3])

@pytest.mark.asyncio
async def test_get_conversation_context_with_memory(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_conversation_memory.return_value = {
        'conversation_summary': 'Previous discussion about course requirements'
    }
    
    result = await manager.get_conversation_context('U123456')
    
    assert 'Previous conversation context:' in result
    assert 'Previous discussion about course requirements' in result

@pytest.mark.asyncio
async def test_get_conversation_context_no_memory(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_conversation_memory.return_value = None
    
    result = await manager.get_conversation_context('U123456')
    
    assert result == ""

@pytest.mark.asyncio
async def test_add_message_with_compression(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_unprocessed_messages.return_value = [
        {'id': 1}, {'id': 2}, {'id': 3}, {'id': 4}
    ]
    
    mock_db.get_conversation_memory.return_value = None
    mock_ollama.generate_response.return_value = 'New summary'
    
    await manager.add_message('U123456', 'Test message', 'Test response')
    
    mock_db.add_raw_message.assert_called_once_with('U123456', 'Test message', 'Test response')
    mock_db.update_conversation_memory.assert_called_once()

@pytest.mark.asyncio
async def test_add_message_without_compression(memory_manager):
    manager, mock_db, mock_ollama = memory_manager
    
    mock_db.get_unprocessed_messages.return_value = [{'id': 1}]
    
    await manager.add_message('U123456', 'Test message', 'Test response')
    
    mock_db.add_raw_message.assert_called_once_with('U123456', 'Test message', 'Test response')
    mock_db.update_conversation_memory.assert_not_called()

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.slack.bot import PantherSlackBot

@pytest.fixture
async def mock_bot():
    with patch('src.slack.bot.load_slack_config') as mock_config, \
         patch('src.slack.bot.load_config') as mock_rag_config, \
         patch('src.slack.bot.UnifiedRAG') as mock_rag, \
         patch('src.slack.bot.StudentProfileManager') as mock_student, \
         patch('src.slack.bot.MemoryInterface') as mock_memory:
        
        mock_config.return_value.bot_token = "test_token"
        mock_config.return_value.app_token = "test_app_token"
        
        bot = PantherSlackBot()
        bot.student_manager = AsyncMock()
        bot.memory_interface = AsyncMock()
        
        yield bot

@pytest.mark.asyncio
async def test_validate_user_access_valid_user(mock_bot):
    bot = mock_bot
    
    assert bot._validate_user_access("U1234567890") is True
    assert bot._validate_user_access("UABCDEF123") is True

@pytest.mark.asyncio
async def test_validate_user_access_invalid_user(mock_bot):
    bot = mock_bot
    
    assert bot._validate_user_access("") is False
    assert bot._validate_user_access(None) is False
    assert bot._validate_user_access("invalid") is False
    assert bot._validate_user_access("U123") is False
    assert bot._validate_user_access("X1234567890") is False
    assert bot._validate_user_access("U123456789!") is False

@pytest.mark.asyncio
async def test_get_user_context_invalid_user_blocked(mock_bot):
    bot = mock_bot
    bot.logger = AsyncMock()
    
    result = await bot._get_user_context("invalid_user")
    
    assert result == {'program': None, 'year': None}
    bot.logger.warning.assert_called_once()

@pytest.mark.asyncio
async def test_get_user_context_valid_user_allowed(mock_bot):
    bot = mock_bot
    bot.student_manager.get_student_profile.return_value = {
        'major': 'Computer Science',
        'catalog_year': 2024
    }
    
    result = await bot._get_user_context("U1234567890")
    
    assert result['program'] == 'Computer Science'
    assert result['year'] == 2024

@pytest.mark.asyncio
async def test_memory_interface_blocks_invalid_users():
    from src.memory.memory_interface import MemoryInterface
    
    with patch('src.memory.memory_interface.DatabaseManager') as mock_db:
        mock_db_instance = AsyncMock()
        mock_db_instance._validate_slack_user_id.return_value = False
        mock_db.return_value = mock_db_instance
        
        interface = MemoryInterface()
        interface.db_manager = mock_db_instance
        
        await interface.add_conversation_turn("invalid_user", "test", "response")
        
        mock_db_instance.add_raw_message.assert_not_called()

@pytest.mark.asyncio 
async def test_database_validation_prevents_cross_contamination():
    from src.memory.database import DatabaseManager
    
    db = DatabaseManager()
    
    assert db._validate_slack_user_id("U1234567890") is True
    assert db._validate_slack_user_id("invalid") is False
    assert db._validate_slack_user_id("") is False
    assert db._validate_slack_user_id(None) is False

@pytest.mark.asyncio
async def test_profile_setup_requires_valid_user_format(mock_bot):
    bot = mock_bot
    say_mock = AsyncMock()
    
    await bot._handle_user_message("Major: Computer Science", "invalid_user", say_mock)
    
    say_mock.assert_called_with("Sorry, I encountered an error. Please try again.")

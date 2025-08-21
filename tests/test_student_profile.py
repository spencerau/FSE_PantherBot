import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from src.memory.student_profile import StudentProfileManager

@pytest.fixture
async def profile_manager():
    with patch('src.memory.student_profile.DatabaseManager') as mock_db:
        mock_db_instance = AsyncMock()
        mock_db.return_value = mock_db_instance
        
        manager = StudentProfileManager()
        manager.db_manager = mock_db_instance
        await manager.initialize()
        
        yield manager, mock_db_instance

@pytest.mark.asyncio
async def test_is_new_student_true(profile_manager):
    manager, mock_db = profile_manager
    
    mock_db.get_student.return_value = None
    
    result = await manager.is_new_student('U123456')
    
    assert result is True

@pytest.mark.asyncio
async def test_is_new_student_false(profile_manager):
    manager, mock_db = profile_manager
    
    mock_db.get_student.return_value = {'slack_user_id': 'U123456'}
    
    result = await manager.is_new_student('U123456')
    
    assert result is False

@pytest.mark.asyncio
async def test_create_student_profile_valid(profile_manager):
    manager, mock_db = profile_manager
    
    mock_db.create_student.return_value = True
    
    success, message = await manager.create_student_profile('U123456', 'Computer Science', 2024)
    
    assert success is True
    assert "successfully" in message

@pytest.mark.asyncio
async def test_create_student_profile_invalid_major(profile_manager):
    manager, mock_db = profile_manager
    
    success, message = await manager.create_student_profile('U123456', 'Invalid Major', 2024)
    
    assert success is False
    assert "Invalid major" in message

@pytest.mark.asyncio
async def test_create_student_profile_invalid_year(profile_manager):
    manager, mock_db = profile_manager
    
    success, message = await manager.create_student_profile('U123456', 'Computer Science', 2021)
    
    assert success is False
    assert "Invalid catalog year" in message

@pytest.mark.asyncio
async def test_update_student_profile_major(profile_manager):
    manager, mock_db = profile_manager
    
    mock_db.update_student.return_value = True
    
    success, message = await manager.update_student_profile('U123456', major='Data Science')
    
    assert success is True
    mock_db.update_student.assert_called_with('U123456', 'Data Science', None)

@pytest.mark.asyncio
async def test_update_student_profile_catalog_year(profile_manager):
    manager, mock_db = profile_manager
    
    mock_db.update_student.return_value = True
    
    success, message = await manager.update_student_profile('U123456', catalog_year=2025)
    
    assert success is True
    mock_db.update_student.assert_called_with('U123456', None, 2025)

@pytest.mark.asyncio
async def test_get_valid_majors(profile_manager):
    manager, mock_db = profile_manager
    
    majors = manager.get_valid_majors()
    
    assert 'Computer Science' in majors
    assert 'Data Science' in majors
    assert len(majors) == 5

@pytest.mark.asyncio
async def test_get_valid_catalog_years(profile_manager):
    manager, mock_db = profile_manager
    
    years = manager.get_valid_catalog_years()
    
    assert 2024 in years
    assert 2025 in years
    assert len(years) == 4

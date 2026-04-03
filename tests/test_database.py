import pytest
from unittest.mock import patch

from fse_memory.fse_student_manager import FSEStudentManager


@pytest.fixture
def manager():
    return FSEStudentManager(config=None)


@pytest.mark.asyncio
async def test_is_new_student_true(manager):
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=None):
        result = await manager.is_new_student('U1234567890')
    assert result is True


@pytest.mark.asyncio
async def test_is_new_student_false(manager):
    profile = {'user_id': 'U1234567890', 'major': 'Computer Science', 'catalog_year': 2024}
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=profile):
        result = await manager.is_new_student('U1234567890')
    assert result is False


@pytest.mark.asyncio
async def test_has_incomplete_profile_no_profile(manager):
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=None):
        result = await manager.has_incomplete_profile('U1234567890')
    assert result is False


@pytest.mark.asyncio
async def test_has_incomplete_profile_missing_major(manager):
    profile = {'user_id': 'U1234567890', 'major': None, 'catalog_year': 2024}
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=profile):
        result = await manager.has_incomplete_profile('U1234567890')
    assert result is True


@pytest.mark.asyncio
async def test_has_incomplete_profile_complete(manager):
    profile = {'user_id': 'U1234567890', 'major': 'Computer Science', 'catalog_year': 2024}
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=profile):
        result = await manager.has_incomplete_profile('U1234567890')
    assert result is False


@pytest.mark.asyncio
async def test_create_student_profile_success(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, msg = await manager.create_student_profile('U1234567890', 'Computer Science', 2024)
    assert success is True
    assert 'successfully' in msg.lower()


@pytest.mark.asyncio
async def test_create_student_profile_invalid_major(manager):
    success, msg = await manager.create_student_profile('U1234567890', 'Underwater Basket Weaving', 2024)
    assert success is False
    assert 'Invalid major' in msg


@pytest.mark.asyncio
async def test_create_student_profile_invalid_year(manager):
    success, msg = await manager.create_student_profile('U1234567890', 'Computer Science', 2019)
    assert success is False
    assert 'Invalid catalog year' in msg


@pytest.mark.asyncio
async def test_create_student_profile_accepts_all_valid_majors(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        for major in FSEStudentManager.VALID_MAJORS:
            success, _ = await manager.create_student_profile('U1234567890', major, 2024)
            assert success is True, f"Expected success for major: {major}"


@pytest.mark.asyncio
async def test_update_student_profile_major(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True) as mock_upsert:
        success, _ = await manager.update_student_profile('U1234567890', major='Data Science')
    assert success is True
    mock_upsert.assert_called_once()


@pytest.mark.asyncio
async def test_update_student_profile_invalid_major(manager):
    success, msg = await manager.update_student_profile('U1234567890', major='Invalid Major')
    assert success is False
    assert 'Invalid major' in msg


@pytest.mark.asyncio
async def test_update_student_profile_catalog_year(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, _ = await manager.update_student_profile('U1234567890', catalog_year=2025)
    assert success is True


def test_get_valid_majors(manager):
    majors = manager.get_valid_majors()
    assert 'Computer Science' in majors
    assert 'Data Science' in majors
    assert 'Software Engineering' in majors
    assert 'Electrical Engineering' in majors
    assert 'Computer Engineering' in majors
    assert len(majors) == 5


def test_get_valid_catalog_years(manager):
    years = manager.get_valid_catalog_years()
    assert 2022 in years
    assert 2023 in years
    assert 2024 in years
    assert 2025 in years
    assert len(years) == 4

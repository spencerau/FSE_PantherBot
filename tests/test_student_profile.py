import pytest
from unittest.mock import patch

from fse_memory.fse_student_manager import FSEStudentManager


@pytest.fixture
def manager():
    return FSEStudentManager(config=None)


def test_parse_major_full_name(manager):
    assert manager.parse_major_input("Computer Science") == "Computer Science"
    assert manager.parse_major_input("Data Science") == "Data Science"


def test_parse_major_short_code(manager):
    assert manager.parse_major_input("cs") == "Computer Science"
    assert manager.parse_major_input("ce") == "Computer Engineering"
    assert manager.parse_major_input("ds") == "Data Science"
    assert manager.parse_major_input("se") == "Software Engineering"
    assert manager.parse_major_input("ee") == "Electrical Engineering"


def test_parse_major_numeric_code(manager):
    assert manager.parse_major_input("1") == "Computer Science"
    assert manager.parse_major_input("2") == "Computer Engineering"


def test_parse_major_with_prefix(manager):
    result = manager.parse_major_input("Major: Computer Science")
    assert result == "Computer Science"


def test_parse_major_invalid_returns_none(manager):
    assert manager.parse_major_input("Underwater Basket Weaving") is None
    assert manager.parse_major_input("invalid") is None
    assert manager.parse_major_input("") is None


def test_parse_catalog_year_valid(manager):
    assert manager.parse_catalog_year_input("2024") == 2024
    assert manager.parse_catalog_year_input("2022") == 2022
    assert manager.parse_catalog_year_input("catalog year: 2025") == 2025


def test_parse_catalog_year_invalid(manager):
    assert manager.parse_catalog_year_input("2019") is None
    assert manager.parse_catalog_year_input("no year here") is None


def test_parse_profile_input_both(manager):
    major, year = manager.parse_profile_input("Computer Science, 2024")
    assert major == "Computer Science"
    assert year == 2024


def test_parse_profile_input_major_only(manager):
    major, year = manager.parse_profile_input("cs")
    assert major == "Computer Science"
    assert year is None


@pytest.mark.asyncio
async def test_create_student_profile_valid(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, message = await manager.create_student_profile('U123456', 'Computer Science', 2024)
    assert success is True
    assert 'successfully' in message.lower()


@pytest.mark.asyncio
async def test_create_student_profile_invalid_major(manager):
    success, message = await manager.create_student_profile('U123456', 'Invalid Major', 2024)
    assert success is False
    assert 'Invalid major' in message


@pytest.mark.asyncio
async def test_create_student_profile_invalid_year(manager):
    success, message = await manager.create_student_profile('U123456', 'Computer Science', 2021)
    assert success is False
    assert 'Invalid catalog year' in message


@pytest.mark.asyncio
async def test_is_new_student_true(manager):
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=None):
        result = await manager.is_new_student('U123456')
    assert result is True


@pytest.mark.asyncio
async def test_is_new_student_false(manager):
    profile = {'user_id': 'U123456', 'major': 'Computer Science', 'catalog_year': 2024}
    with patch('fse_memory.fse_student_manager.get_student_profile', return_value=profile):
        result = await manager.is_new_student('U123456')
    assert result is False


@pytest.mark.asyncio
async def test_update_student_profile_major(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, _ = await manager.update_student_profile('U123456', major='Data Science')
    assert success is True


@pytest.mark.asyncio
async def test_update_student_profile_catalog_year(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, _ = await manager.update_student_profile('U123456', catalog_year=2025)
    assert success is True


def test_get_valid_majors(manager):
    majors = manager.get_valid_majors()
    assert 'Computer Science' in majors
    assert 'Data Science' in majors
    assert len(majors) == 5


def test_get_valid_catalog_years(manager):
    years = manager.get_valid_catalog_years()
    assert 2024 in years
    assert 2025 in years
    assert len(years) == 4

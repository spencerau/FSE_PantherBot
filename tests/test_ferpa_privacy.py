import pytest
from unittest.mock import patch

from fse_memory.fse_student_manager import FSEStudentManager

FSE_VALID_MAJORS = [
    "Computer Science",
    "Computer Engineering",
    "Data Science",
    "Software Engineering",
    "Electrical Engineering",
]

FSE_VALID_YEARS = [2022, 2023, 2024, 2025]


@pytest.fixture
def manager():
    return FSEStudentManager(config=None)


def test_parse_major_accepts_only_valid_fse_majors(manager):
    for major in FSE_VALID_MAJORS:
        result = manager.parse_major_input(major)
        assert result == major


def test_parse_major_rejects_arbitrary_strings(manager):
    garbage = [
        "History", "Biology", "Art",
        "DROP TABLE students;",
        "'; SELECT * FROM students; --",
        "../../etc/passwd",
        "", "   ",
    ]
    for bad_input in garbage:
        result = manager.parse_major_input(bad_input.strip())
        assert result is None, f"Expected None for input: {repr(bad_input)}"


def test_parse_major_short_codes_map_to_valid_majors(manager):
    code_to_major = {
        "cs": "Computer Science",
        "ce": "Computer Engineering",
        "ds": "Data Science",
        "se": "Software Engineering",
        "ee": "Electrical Engineering",
    }
    for code, expected in code_to_major.items():
        assert manager.parse_major_input(code) == expected


def test_parse_catalog_year_accepts_valid_years(manager):
    for year in FSE_VALID_YEARS:
        assert manager.parse_catalog_year_input(str(year)) == year


def test_parse_catalog_year_rejects_out_of_range(manager):
    invalid_years = ["2019", "2020", "2021", "2026", "2030", "1999", "9999"]
    for y in invalid_years:
        assert manager.parse_catalog_year_input(y) is None, f"Expected None for year: {y}"


@pytest.mark.asyncio
async def test_profile_creation_rejects_invalid_major_before_db_write(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile') as mock_upsert:
        success, _ = await manager.create_student_profile('U1234567890', 'Philosophy', 2024)
    assert success is False
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_profile_creation_rejects_invalid_year_before_db_write(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile') as mock_upsert:
        success, _ = await manager.create_student_profile('U1234567890', 'Computer Science', 2019)
    assert success is False
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_profile_creation_writes_db_only_for_valid_data(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True) as mock_upsert:
        success, _ = await manager.create_student_profile('U1234567890', 'Computer Science', 2024)
    assert success is True
    mock_upsert.assert_called_once()


@pytest.mark.asyncio
async def test_update_profile_rejects_invalid_major(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile') as mock_upsert:
        success, _ = await manager.update_student_profile('U1234567890', major='Not A Major')
    assert success is False
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_update_profile_rejects_invalid_year(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile') as mock_upsert:
        success, _ = await manager.update_student_profile('U1234567890', catalog_year=1999)
    assert success is False
    mock_upsert.assert_not_called()


@pytest.mark.asyncio
async def test_profile_isolation_different_users(manager):
    calls = []

    def capture_upsert(user_id, major, catalog_year, minor, additional_program_asked, config):
        calls.append(user_id)
        return True

    with patch('fse_memory.fse_student_manager.upsert_student_profile', side_effect=capture_upsert):
        await manager.create_student_profile('U0000000001', 'Computer Science', 2024)
        await manager.create_student_profile('U0000000002', 'Data Science', 2025)

    assert calls == ['U0000000001', 'U0000000002']

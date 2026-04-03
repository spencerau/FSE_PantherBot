import pytest
from unittest.mock import patch, MagicMock

from fse_memory.fse_student_manager import FSEStudentManager
from fse_memory.fse_chat_session import FSEChatSession


# ---------------------------------------------------------------------------
# FSEStudentManager — input parsing (no DB required)
# ---------------------------------------------------------------------------

@pytest.fixture
def manager():
    return FSEStudentManager(config=None)


def test_parse_major_from_natural_text(manager):
    assert manager.parse_major_input("I am studying Computer Science") is None
    assert manager.parse_major_input("cs") == "Computer Science"
    assert manager.parse_major_input("Major: Software Engineering") == "Software Engineering"


def test_parse_catalog_year_from_text(manager):
    assert manager.parse_catalog_year_input("I started in 2023") == 2023
    assert manager.parse_catalog_year_input("year: 2025") == 2025
    assert manager.parse_catalog_year_input("2021") is None


@pytest.mark.asyncio
async def test_create_profile_from_text_both(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, _ = await manager.create_student_profile_from_text(
            'U1234567890', "cs, 2024"
        )
    assert success is True


@pytest.mark.asyncio
async def test_create_profile_from_text_major_only(manager):
    with patch('fse_memory.fse_student_manager.upsert_student_profile', return_value=True):
        success, msg = await manager.create_student_profile_from_text(
            'U1234567890', "Computer Science"
        )
    assert success is True
    assert 'catalog year' in msg.lower()


@pytest.mark.asyncio
async def test_create_profile_from_text_unrecognized(manager):
    success, msg = await manager.create_student_profile_from_text(
        'U1234567890', "gibberish text"
    )
    assert success is False


# ---------------------------------------------------------------------------
# FSEChatSession — integration tests (requires PostgreSQL + Ollama)
# ---------------------------------------------------------------------------

TEST_USER = "test_fse_memory_user"


@pytest.fixture(scope="module")
def fse_config():
    from fse_utils.config_loader import load_config
    cfg = load_config()
    cfg.setdefault('memory', {})['compression_trigger'] = 2
    return cfg


@pytest.fixture(scope="module")
def session(fse_config):
    try:
        from fse_memory.fse_chat_session import init_all_schemas
        init_all_schemas(fse_config)
        sess = FSEChatSession(user_id=TEST_USER, config=fse_config)
    except Exception as e:
        pytest.skip(f"PostgreSQL not available: {e}")
        return
    yield sess

    from core_rag.memory.db import get_connection
    with get_connection(fse_config) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (TEST_USER,))
            cur.execute("DELETE FROM student_profiles WHERE user_id = %s", (TEST_USER,))


@pytest.mark.integration
def test_session_creation(session):
    assert session.session_id is not None
    assert session.user_id == TEST_USER


@pytest.mark.integration
def test_get_history_empty(session):
    from core_rag.memory import session_store
    history = session_store.get_active_messages(session.session_id, session.config)
    assert isinstance(history, list)


@pytest.mark.integration
def test_session_profile_update(session):
    success = session.update_profile(major="Computer Science", catalog_year=2024)
    assert success is True


@pytest.mark.integration
def test_session_get_profile(session):
    profile = session.get_profile()
    if profile is not None:
        assert 'major' in profile or 'user_id' in profile


@pytest.mark.integration
def test_session_resume(fse_config, session):
    resumed = FSEChatSession(
        user_id=TEST_USER,
        session_id=session.session_id,
        config=fse_config,
    )
    assert resumed.session_id == session.session_id
    assert resumed.user_id == TEST_USER

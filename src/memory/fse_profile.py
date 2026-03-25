from typing import Optional, Dict, List
from pathlib import Path
from core_rag.memory.db import get_connection


def init_fse_schema(config: dict = None):
    schema_path = Path(__file__).parent / 'fse_schema.sql'
    sql = schema_path.read_text()
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def get_student_profile(user_id: str, config: dict = None) -> Optional[Dict]:
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT user_id, major, catalog_year, minor, additional_program_asked, '
                'created_at, updated_at '
                'FROM student_profiles WHERE user_id = %s',
                (user_id,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                'user_id': row[0],
                'major': row[1],
                'catalog_year': row[2],
                'minor': row[3],
                'additional_program_asked': row[4],
                'created_at': row[5],
                'updated_at': row[6],
            }


def upsert_student_profile(
    user_id: str,
    major: str = None,
    catalog_year: int = None,
    minor: str = None,
    additional_program_asked: bool = None,
    config: dict = None,
) -> bool:
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO student_profiles (user_id, major, catalog_year, minor, additional_program_asked)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    major = COALESCE(EXCLUDED.major, student_profiles.major),
                    catalog_year = COALESCE(EXCLUDED.catalog_year, student_profiles.catalog_year),
                    minor = COALESCE(EXCLUDED.minor, student_profiles.minor),
                    additional_program_asked = COALESCE(
                        EXCLUDED.additional_program_asked,
                        student_profiles.additional_program_asked
                    ),
                    updated_at = NOW()
            ''', (user_id, major, catalog_year, minor, additional_program_asked))
    return True


def clear_user_sessions(user_id: str, config: dict = None):
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM sessions WHERE user_id = %s', (user_id,))


def delete_student_profile(user_id: str, config: dict = None):
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM sessions WHERE user_id = %s', (user_id,))
            cur.execute('DELETE FROM student_profiles WHERE user_id = %s', (user_id,))


def get_latest_session_id(user_id: str, config: dict = None) -> Optional[str]:
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT session_id FROM sessions WHERE user_id = %s '
                'ORDER BY updated_at DESC LIMIT 1',
                (user_id,)
            )
            row = cur.fetchone()
            return str(row[0]) if row else None


def add_citation(
    session_id: str,
    message_index: int,
    collection: str,
    metadata: dict,
    config: dict = None,
):
    import json
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                INSERT INTO citations (session_id, message_index, collection, metadata)
                VALUES (%s::uuid, %s, %s, %s)
            ''', (session_id, message_index, collection, json.dumps(metadata)))


def get_citations(session_id: str, message_index: int, config: dict = None) -> List[Dict]:
    import json
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                'SELECT collection, metadata FROM citations '
                'WHERE session_id = %s::uuid AND message_index = %s '
                'ORDER BY id',
                (session_id, message_index)
            )
            rows = cur.fetchall()
            return [{'collection': r[0], 'metadata': json.loads(r[1])} for r in rows]


def get_last_assistant_message_index(session_id: str, config: dict = None) -> Optional[int]:
    with get_connection(config) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT message_index FROM messages "
                "WHERE session_id = %s::uuid AND role = 'assistant' "
                "ORDER BY message_index DESC LIMIT 1",
                (session_id,)
            )
            row = cur.fetchone()
            return row[0] if row else None

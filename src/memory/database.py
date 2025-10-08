import os
import asyncio
import asyncpg
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.connection_pool = None
        
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
        
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', '5432')),
            'database': os.getenv('POSTGRES_DB', 'pantherbot'),
            'user': os.getenv('POSTGRES_USER', 'pantherbot'),
            'password': os.getenv('POSTGRES_PASSWORD')
        }

    async def initialize(self):
        self.connection_pool = await asyncpg.create_pool(**self.db_config)
        await self._create_tables()

    def _validate_slack_user_id(self, slack_user_id: str) -> bool:
        if not slack_user_id or not isinstance(slack_user_id, str):
            return False
        if not slack_user_id.startswith('U') or len(slack_user_id) < 9:
            return False
        return slack_user_id.isalnum()

    async def get_student(self, slack_user_id: str) -> Optional[Dict]:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return None
            
        async with self.connection_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT slack_user_id, major, catalog_year, minor, additional_program_asked, created_at, updated_at FROM students WHERE slack_user_id = $1',
                slack_user_id
            )
            return dict(row) if row else None

    async def create_student(self, slack_user_id: str, major: str = None, catalog_year: int = None, minor: str = None, additional_program_asked: bool = False) -> bool:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False
            
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO students (slack_user_id, major, catalog_year, minor, additional_program_asked) VALUES ($1, $2, $3, $4, $5)',
                    slack_user_id, major, catalog_year, minor, additional_program_asked
                )
            logger.info(f"Created student profile for user {slack_user_id[:3]}***")
            return True
        except Exception as e:
            logger.error(f"Error creating student: {e}")
            return False

    async def update_student(
        self,
        slack_user_id: str,
        major: str = None,
        catalog_year: int = None,
        minor: str = None,
        additional_program_asked: Optional[bool] = None
    ) -> bool:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False
            
        try:
            async with self.connection_pool.acquire() as conn:
                updates = []
                values = []
                param_index = 2

                if major is not None:
                    updates.append(f"major = ${param_index}")
                    values.append(major)
                    param_index += 1

                if catalog_year is not None:
                    updates.append(f"catalog_year = ${param_index}")
                    values.append(catalog_year)
                    param_index += 1

                if minor is not None:
                    updates.append(f"minor = ${param_index}")
                    values.append(minor)
                    param_index += 1

                if additional_program_asked is not None:
                    updates.append(f"additional_program_asked = ${param_index}")
                    values.append(additional_program_asked)
                    param_index += 1

                if not updates:
                    return True

                updates.append("updated_at = CURRENT_TIMESTAMP")
                query = f"UPDATE students SET {', '.join(updates)} WHERE slack_user_id = $1"
                await conn.execute(query, slack_user_id, *values)
            logger.info(f"Updated student profile for user {slack_user_id[:3]}***")
            return True
        except Exception as e:
            logger.error(f"Error updating student: {e}")
            return False

    async def create_user_name(self, slack_user_id: str, first_name: str = None, last_name: str = None) -> bool:
        """Create a new user name record"""
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False

        try:
            async with self.connection_pool.acquire() as conn:
                await conn.execute(
                    '''INSERT INTO user_names (slack_user_id, first_name, last_name) 
                       VALUES ($1, $2, $3)
                       ON CONFLICT (slack_user_id) DO UPDATE SET
                       first_name = EXCLUDED.first_name,
                       last_name = EXCLUDED.last_name,
                       updated_at = CURRENT_TIMESTAMP''',
                    slack_user_id, first_name, last_name
                )
            logger.info(f"Created/updated user name for {slack_user_id[:3]}***")
            return True
        except Exception as e:
            logger.error(f"Error creating user name: {e}")
            return False

    async def get_user_name(self, slack_user_id: str) -> Optional[Dict]:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return None

        try:
            async with self.connection_pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT slack_user_id, first_name, last_name, created_at, updated_at FROM user_names WHERE slack_user_id = $1',
                    slack_user_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user name: {e}")
            return None

    async def add_raw_message(self, slack_user_id: str, message_text: str, response_text: str = None, citations: list = None):
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return
            
        import json
        citations_json = json.dumps(citations) if citations else None
            
        async with self.connection_pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO raw_messages (slack_user_id, message_text, response_text, citations) VALUES ($1, $2, $3, $4)',
                slack_user_id, message_text, response_text, citations_json
            )

    async def get_unprocessed_messages(self, slack_user_id: str) -> List[Dict]:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return []
            
        import json
        async with self.connection_pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT id, slack_user_id, message_text, response_text, citations, timestamp, processed FROM raw_messages WHERE slack_user_id = $1 AND processed = FALSE ORDER BY timestamp',
                slack_user_id
            )
            result = []
            for row in rows:
                row_dict = dict(row)
                if row_dict['citations']:
                    row_dict['citations'] = json.loads(row_dict['citations'])
                result.append(row_dict)
            return result

    async def get_conversation_memory(self, slack_user_id: str) -> Optional[Dict]:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return None
            
        async with self.connection_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT id, slack_user_id, conversation_summary, message_count, last_updated, created_at FROM conversation_memory WHERE slack_user_id = $1 ORDER BY last_updated DESC LIMIT 1',
                slack_user_id
            )
            return dict(row) if row else None

    async def update_conversation_memory(self, slack_user_id: str, summary: str, message_count: int):
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return
            
        async with self.connection_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT id FROM conversation_memory WHERE slack_user_id = $1',
                slack_user_id
            )
            
            if existing:
                await conn.execute(
                    'UPDATE conversation_memory SET conversation_summary = $2, message_count = $3, last_updated = CURRENT_TIMESTAMP WHERE slack_user_id = $1',
                    slack_user_id, summary, message_count
                )
            else:
                await conn.execute(
                    'INSERT INTO conversation_memory (slack_user_id, conversation_summary, message_count) VALUES ($1, $2, $3)',
                    slack_user_id, summary, message_count
                )

    async def get_last_message_citations(self, slack_user_id: str) -> Optional[Dict]:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return None
            
        import json
        async with self.connection_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT message_text, response_text, citations, timestamp FROM raw_messages WHERE slack_user_id = $1 ORDER BY timestamp DESC LIMIT 1',
                slack_user_id
            )
            if row:
                result = dict(row)
                if result['citations']:
                    result['citations'] = json.loads(result['citations'])
                return result
            return None

    async def mark_messages_processed(self, message_ids: List[int]):
        async with self.connection_pool.acquire() as conn:
            await conn.execute(
                'UPDATE raw_messages SET processed = TRUE WHERE id = ANY($1)',
                message_ids
            )

    async def clear_user_message_history(self, slack_user_id: str) -> bool:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False
            
        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        'DELETE FROM conversation_memory WHERE slack_user_id = $1',
                        slack_user_id
                    )
                    
            logger.info(f"Cleared conversation history for user {slack_user_id[:3]}*** (kept raw messages for auditing)")
            return True
        except Exception as e:
            logger.error(f"Error clearing message history: {e}")
            return False

    async def delete_user_profile(self, slack_user_id: str) -> bool:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False
            
        try:
            async with self.connection_pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute(
                        'DELETE FROM raw_messages WHERE slack_user_id = $1',
                        slack_user_id
                    )
                    
                    await conn.execute(
                        'DELETE FROM conversation_memory WHERE slack_user_id = $1',
                        slack_user_id
                    )
                    
                    await conn.execute(
                        'DELETE FROM students WHERE slack_user_id = $1',
                        slack_user_id
                    )
                    
                    await conn.execute(
                        'DELETE FROM user_names WHERE slack_user_id = $1',
                        slack_user_id
                    )
                    
            logger.info(f"Deleted complete profile for user {slack_user_id[:3]}***")
            return True
        except Exception as e:
            logger.error(f"Error deleting user profile: {e}")
            return False

    async def _create_tables(self):
        async with self.connection_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_names (
                    slack_user_id VARCHAR(20) PRIMARY KEY,
                    first_name VARCHAR(100),
                    last_name VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    slack_user_id VARCHAR(20) PRIMARY KEY REFERENCES user_names(slack_user_id) ON DELETE CASCADE,
                    major VARCHAR(100),
                    catalog_year INTEGER,
                    minor VARCHAR(100),
                    additional_program_asked BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await conn.execute('''
                ALTER TABLE students
                ADD COLUMN IF NOT EXISTS minor VARCHAR(100)
            ''')

            await conn.execute('''
                ALTER TABLE students
                ADD COLUMN IF NOT EXISTS additional_program_asked BOOLEAN DEFAULT FALSE
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS conversation_memory (
                    id SERIAL PRIMARY KEY,
                    slack_user_id VARCHAR(20) REFERENCES students(slack_user_id) ON DELETE CASCADE,
                    conversation_summary TEXT,
                    message_count INTEGER DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS raw_messages (
                    id SERIAL PRIMARY KEY,
                    slack_user_id VARCHAR(20) REFERENCES students(slack_user_id) ON DELETE CASCADE,
                    message_text TEXT,
                    response_text TEXT,
                    citations JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
            ''')
            
            await conn.execute('''
                ALTER TABLE raw_messages 
                ADD COLUMN IF NOT EXISTS citations JSONB
            ''')
            
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_raw_messages_user_processed 
                ON raw_messages(slack_user_id, processed)
            ''')
            
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_conversation_memory_user 
                ON conversation_memory(slack_user_id, last_updated)
            ''')

    async def close(self):
        if self.connection_pool:
            await self.connection_pool.close()

    async def close(self):
        if self.connection_pool:
            await self.connection_pool.close()

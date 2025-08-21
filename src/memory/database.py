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
            'password': os.getenv('POSTGRES_PASSWORD', 'pantherbot_secure_2025')
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
                'SELECT slack_user_id, major, catalog_year, created_at, updated_at FROM students WHERE slack_user_id = $1',
                slack_user_id
            )
            return dict(row) if row else None

    async def create_student(self, slack_user_id: str, major: str = None, catalog_year: int = None) -> bool:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False
            
        try:
            async with self.connection_pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO students (slack_user_id, major, catalog_year) VALUES ($1, $2, $3)',
                    slack_user_id, major, catalog_year
                )
            logger.info(f"Created student profile for user {slack_user_id[:3]}***")
            return True
        except Exception as e:
            logger.error(f"Error creating student: {e}")
            return False

    async def update_student(self, slack_user_id: str, major: str = None, catalog_year: int = None) -> bool:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return False
            
        try:
            async with self.connection_pool.acquire() as conn:
                if major and catalog_year:
                    await conn.execute(
                        'UPDATE students SET major = $2, catalog_year = $3, updated_at = CURRENT_TIMESTAMP WHERE slack_user_id = $1',
                        slack_user_id, major, catalog_year
                    )
                elif major:
                    await conn.execute(
                        'UPDATE students SET major = $2, updated_at = CURRENT_TIMESTAMP WHERE slack_user_id = $1',
                        slack_user_id, major
                    )
                elif catalog_year:
                    await conn.execute(
                        'UPDATE students SET catalog_year = $2, updated_at = CURRENT_TIMESTAMP WHERE slack_user_id = $1',
                        slack_user_id, catalog_year
                    )
            logger.info(f"Updated student profile for user {slack_user_id[:3]}***")
            return True
        except Exception as e:
            logger.error(f"Error updating student: {e}")
            return False

    async def add_raw_message(self, slack_user_id: str, message_text: str, response_text: str = None):
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return
            
        async with self.connection_pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO raw_messages (slack_user_id, message_text, response_text) VALUES ($1, $2, $3)',
                slack_user_id, message_text, response_text
            )

    async def get_unprocessed_messages(self, slack_user_id: str) -> List[Dict]:
        if not self._validate_slack_user_id(slack_user_id):
            logger.warning(f"Invalid slack_user_id format: {slack_user_id}")
            return []
            
        async with self.connection_pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT id, slack_user_id, message_text, response_text, timestamp, processed FROM raw_messages WHERE slack_user_id = $1 AND processed = FALSE ORDER BY timestamp',
                slack_user_id
            )
            return [dict(row) for row in rows]

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

    async def mark_messages_processed(self, message_ids: List[int]):
        async with self.connection_pool.acquire() as conn:
            await conn.execute(
                'UPDATE raw_messages SET processed = TRUE WHERE id = ANY($1)',
                message_ids
            )

    async def _create_tables(self):
        async with self.connection_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    slack_user_id VARCHAR(20) PRIMARY KEY,
                    major VARCHAR(100),
                    catalog_year INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
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
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
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

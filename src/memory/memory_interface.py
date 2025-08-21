import asyncio
from typing import Dict, Optional
import logging
from pathlib import Path
from dotenv import load_dotenv
from memory.database import DatabaseManager

logger = logging.getLogger(__name__)

class MemoryInterface:
    def __init__(self):
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            
        self.db_manager = DatabaseManager()

    async def initialize(self):
        await self.db_manager.initialize()

    async def add_conversation_turn(self, user_id: str, user_message: str, bot_response: str):
        if not self.db_manager._validate_slack_user_id(user_id):
            logger.warning(f"Attempted to add conversation for invalid user ID: {user_id}")
            return
        await self.db_manager.add_raw_message(user_id, user_message, bot_response)

    async def get_recent_context(self, user_id: str, max_messages: int = 3) -> str:
        if not self.db_manager._validate_slack_user_id(user_id):
            logger.warning(f"Attempted to get context for invalid user ID: {user_id}")
            return ""
            
        try:
            async with self.db_manager.connection_pool.acquire() as conn:
                recent_messages = await conn.fetch('''
                    SELECT message_text, response_text, timestamp 
                    FROM raw_messages 
                    WHERE slack_user_id = $1 
                    ORDER BY timestamp DESC 
                    LIMIT $2
                ''', user_id, max_messages)
            
            if not recent_messages:
                memory = await self.db_manager.get_conversation_memory(user_id)
                if memory and memory['conversation_summary']:
                    return f"Previous conversation context: {memory['conversation_summary']}"
                return ""
            
            context_parts = []
            for msg in reversed(recent_messages):
                context_parts.append(f"User: {msg['message_text']}")
                if msg['response_text']:
                    context_parts.append(f"Assistant: {msg['response_text'][:200]}...")
            
            context = "\n".join(context_parts[-6:])
            
            memory = await self.db_manager.get_conversation_memory(user_id)
            if memory and memory['conversation_summary']:
                return f"Previous context: {memory['conversation_summary']}\n\nRecent conversation:\n{context}"
            
            return f"Recent conversation:\n{context}"
            
        except Exception as e:
            logger.error(f"Error getting conversation context: {e}")
            return ""

    async def close(self):
        await self.db_manager.close()

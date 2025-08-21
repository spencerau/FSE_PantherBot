import asyncio
from typing import Dict, List
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))
from utils.ollama_api import OllamaAPI
from memory.database import DatabaseManager

logger = logging.getLogger(__name__)

class ConversationMemoryManager:
    def __init__(self, compression_threshold: int = 10):
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            
        self.db_manager = DatabaseManager()
        self.compression_threshold = compression_threshold
        self.ollama_api = OllamaAPI()

    async def initialize(self):
        await self.db_manager.initialize()

    async def should_compress_memory(self, slack_user_id: str) -> bool:
        unprocessed_messages = await self.db_manager.get_unprocessed_messages(slack_user_id)
        return len(unprocessed_messages) >= self.compression_threshold

    async def compress_conversation_memory(self, slack_user_id: str):
        try:
            unprocessed_messages = await self.db_manager.get_unprocessed_messages(slack_user_id)
            
            if len(unprocessed_messages) < 2:
                return
            
            conversation_text = self._format_messages_for_compression(unprocessed_messages)
            
            existing_memory = await self.db_manager.get_conversation_memory(slack_user_id)
            context = existing_memory['conversation_summary'] if existing_memory else ""
            
            compressed_summary = await self._generate_summary(conversation_text, context)
            
            total_message_count = (existing_memory['message_count'] if existing_memory else 0) + len(unprocessed_messages)
            
            await self.db_manager.update_conversation_memory(
                slack_user_id, 
                compressed_summary, 
                total_message_count
            )
            
            message_ids = [msg['id'] for msg in unprocessed_messages]
            await self.db_manager.mark_messages_processed(message_ids)
            
            logger.info(f"Compressed {len(unprocessed_messages)} messages for user {slack_user_id}")
            
        except Exception as e:
            logger.error(f"Error compressing memory for {slack_user_id}: {e}")

    def _format_messages_for_compression(self, messages: List[Dict]) -> str:
        formatted = []
        for msg in messages:
            formatted.append(f"User: {msg['message_text']}")
            if msg['response_text']:
                formatted.append(f"Assistant: {msg['response_text']}")
        return "\n\n".join(formatted)

    async def _generate_summary(self, conversation_text: str, existing_context: str = "") -> str:
        prompt = f"""
Summarize this academic advising conversation into key points that would be helpful for future interactions:

Previous context: {existing_context}

Recent conversation:
{conversation_text}

Focus on:
- Academic questions asked
- Course requirements discussed
- Registration issues
- Academic goals mentioned
- Any specific concerns or needs

Provide a concise summary that preserves important academic context for future conversations.
"""
        
        try:
            response = await self.ollama_api.generate_response(
                prompt=prompt,
                model="llama3.2:3b",
                temperature=0.3,
                max_tokens=500
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Previous context: {existing_context}\n\nRecent conversation summary: {len(conversation_text.split())} words of academic discussion."

    async def get_conversation_context(self, slack_user_id: str) -> str:
        memory = await self.db_manager.get_conversation_memory(slack_user_id)
        if memory and memory['conversation_summary']:
            return f"Previous conversation context: {memory['conversation_summary']}"
        return ""

    async def add_message(self, slack_user_id: str, message_text: str, response_text: str = None):
        await self.db_manager.add_raw_message(slack_user_id, message_text, response_text)
        
        if await self.should_compress_memory(slack_user_id):
            await self.compress_conversation_memory(slack_user_id)

    async def close(self):
        await self.db_manager.close()

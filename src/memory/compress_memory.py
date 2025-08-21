import asyncio
import logging
from typing import List
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from memory.conversation_manager import ConversationMemoryManager
from memory.database import DatabaseManager

logger = logging.getLogger(__name__)

class MemoryCompressionService:
    def __init__(self, compression_threshold: int = 10):
        self.compression_threshold = compression_threshold
        self.memory_manager = ConversationMemoryManager(compression_threshold)
        self.db_manager = DatabaseManager()

    async def initialize(self):
        await self.memory_manager.initialize()
        await self.db_manager.initialize()

    async def compress_all_user_memories(self):
        try:
            logger.info("Starting memory compression for all users")
            
            async with self.db_manager.connection_pool.acquire() as conn:
                users = await conn.fetch(
                    'SELECT DISTINCT slack_user_id FROM raw_messages WHERE processed = FALSE'
                )
            
            compression_count = 0
            for user_row in users:
                user_id = user_row['slack_user_id']
                
                if await self.memory_manager.should_compress_memory(user_id):
                    await self.memory_manager.compress_conversation_memory(user_id)
                    compression_count += 1
                    logger.info(f"Compressed memory for user {user_id}")
            
            logger.info(f"Memory compression completed. Processed {compression_count} users.")
            return compression_count
            
        except Exception as e:
            logger.error(f"Error during memory compression: {e}")
            return 0

    async def cleanup_old_raw_messages(self, days_old: int = 30):
        try:
            async with self.db_manager.connection_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM raw_messages WHERE processed = TRUE AND timestamp < NOW() - INTERVAL %s DAY',
                    days_old
                )
            
            logger.info(f"Cleaned up old processed messages: {result}")
            
        except Exception as e:
            logger.error(f"Error cleaning up old messages: {e}")

    async def get_compression_stats(self):
        try:
            async with self.db_manager.connection_pool.acquire() as conn:
                stats = await conn.fetchrow('''
                    SELECT 
                        COUNT(DISTINCT slack_user_id) as total_users,
                        COUNT(*) FILTER (WHERE processed = FALSE) as unprocessed_messages,
                        COUNT(*) FILTER (WHERE processed = TRUE) as processed_messages
                    FROM raw_messages
                ''')
                
                memory_stats = await conn.fetchrow('''
                    SELECT 
                        COUNT(*) as users_with_memory,
                        AVG(message_count) as avg_messages_per_user
                    FROM conversation_memory
                ''')
            
            return {
                'total_users': stats['total_users'],
                'unprocessed_messages': stats['unprocessed_messages'],
                'processed_messages': stats['processed_messages'],
                'users_with_memory': memory_stats['users_with_memory'],
                'avg_messages_per_user': float(memory_stats['avg_messages_per_user']) if memory_stats['avg_messages_per_user'] else 0
            }
            
        except Exception as e:
            logger.error(f"Error getting compression stats: {e}")
            return {}

    async def close(self):
        await self.memory_manager.close()
        await self.db_manager.close()

async def run_memory_compression():
    service = MemoryCompressionService()
    
    try:
        await service.initialize()
        
        logger.info("Getting compression stats before processing...")
        stats_before = await service.get_compression_stats()
        logger.info(f"Stats before: {stats_before}")
        
        compression_count = await service.compress_all_user_memories()
        
        logger.info("Getting compression stats after processing...")
        stats_after = await service.get_compression_stats()
        logger.info(f"Stats after: {stats_after}")
        
        await service.cleanup_old_raw_messages()
        
    finally:
        await service.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_memory_compression())

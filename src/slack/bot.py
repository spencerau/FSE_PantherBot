"""
PantherBot Slack Integration
Main Slack bot class for handling messages and interactions.
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))
from config import load_slack_config

sys.path.append(str(Path(__file__).parent.parent))
from retrieval.unified_rag import UnifiedRAG
from utils.config_loader import load_config

class PantherSlackBot:
    
    def __init__(self, slack_bot_token: str = None, slack_app_token: str = None):
        try:
            self.slack_config = load_slack_config()
            self.slack_bot_token = slack_bot_token or self.slack_config.bot_token
            self.slack_app_token = slack_app_token or self.slack_config.app_token
        except ValueError:
            self.slack_config = None
            self.slack_bot_token = slack_bot_token or os.getenv("SLACK_BOT_TOKEN")
            self.slack_app_token = slack_app_token or os.getenv("SLACK_APP_TOKEN")
        
        if not self.slack_bot_token or not self.slack_app_token:
            raise ValueError("Missing required Slack tokens. Set SLACK_BOT_TOKEN and SLACK_APP_TOKEN environment variables.")
        
        self.app = AsyncApp(token=self.slack_bot_token)
        self.client = AsyncWebClient(token=self.slack_bot_token)
        
        self.config = load_config()
        self.rag_system = UnifiedRAG()
        
        self._setup_handlers()
        
        self.handler = AsyncSocketModeHandler(self.app, self.slack_app_token)
        
        self.bot_user_id = None
        self.bot_info = None
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def _setup_handlers(self):
        
        @self.app.message("hello")
        async def handle_hello(message, say):
            await say(f"Hello <@{message['user']}>! I'm PantherBot, your academic advisor assistant. Ask me about course requirements, registration, or academic policies!")
        
        @self.app.message("help")
        async def handle_help(message, say):
            help_text = """
                PantherBot Help

                I can help you with:
                - Course requirements for your major
                - Academic policies and procedures  
                - Registration information
                - 4-year plan guidance
                - General academic questions

                Example questions:
                - "What are the upper division requirements for Computer Science?"
                - "How do I register for classes?"
                - "What courses should I take my freshman year?"
                - "How do I book an appointment with an academic advisor?"

                Just ask me any academic question and I'll do my best to help!
            """
            await say(help_text)
        
        @self.app.event("app_mention")
        async def handle_mention(event, say):
            user_id = event['user']
            text = event['text']
            
            clean_text = self._clean_mention_text(text)
            
            if clean_text.strip():
                await self._process_academic_query(clean_text, user_id, say)
            else:
                await say(f"Hi <@{user_id}>! What academic question can I help you with?")
        
        @self.app.message("")
        async def handle_direct_message(message, say):
            logging.info(f"Received message: {message}")
            
            if message.get('user') == self.bot_user_id:
                logging.info("Skipping message from bot itself")
                return
            
            text = message.get('text', '').strip()
            if not text or text.lower() in ['hello', 'help']:
                logging.info(f"Skipping hello/help message: {text}")
                return
            
            user_id = message['user']
            logging.info(f"Processing academic query from {user_id}: {text}")
            await self._process_academic_query(text, user_id, say)
    
    def _clean_mention_text(self, text: str) -> str:
        if self.bot_user_id:
            mention = f"<@{self.bot_user_id}>"
            text = text.replace(mention, "").strip()
        return text
    
    async def _process_academic_query(self, query: str, user_id: str, say):
        try:
            user_info = await self._get_user_context(user_id)
            
            await say("Let me look that up for you...")
            
            answer, retrieved_chunks = self.rag_system.answer_question(
                query=query,
                student_program=user_info.get('program'),
                student_year=user_info.get('year'),
                top_k=self.config['retrieval']['top_k'],
                enable_reranking=False,
                use_streaming=False
            )
            
            formatted_response = self._format_response(answer, retrieved_chunks)
            
            await say(formatted_response)
            
            self.logger.info(f"Processed query for user {user_id}: {query[:50]}...")
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            await say("Sorry, I encountered an error processing your question. Please try again or contact academic advising directly.")
    
    async def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        if self.slack_config:
            return {
                'program': self.slack_config.student_major,
                'year': self.slack_config.student_catalog_year
            }
        else:
            return {
                'program': os.getenv('STUDENT_MAJOR'),
                'year': os.getenv('STUDENT_CATALOG_YEAR'),
            }
    
    def _format_response(self, response: str, sources: list) -> str:
        formatted = f"PantherBot Academic Assistant\n\n{response}"
        
        if sources:
            formatted += "\n\nSources:\n"
            for i, source in enumerate(sources[:3], 1):
                try:
                    if isinstance(source, dict):
                        metadata = source.get('metadata', {})
                        program = metadata.get('program_full', 'N/A') 
                        year = metadata.get('year', 'N/A')
                        section = metadata.get('section_name', 'N/A')
                        formatted += f"- {program} ({year}) - {section}\n"
                    else:
                        formatted += f"- Source {i}\n"
                except Exception as e:
                    self.logger.error(f"Error formatting source {i}: {e}")
                    formatted += f"- Source {i}\n"
        
        return formatted
    
    async def start(self):
        try:
            logging.info("Testing Slack authentication...")
            auth_response = await self.client.auth_test()
            logging.info(f"Authentication successful! Bot: {auth_response['user']} on {auth_response['team']}")
            
            logging.info("Starting Socket Mode handler...")
            await self.handler.start_async()
            
        except SlackApiError as e:
            logging.error(f"Slack API Error: {e}")
            raise
        except Exception as e:
            logging.error(f"Unexpected error starting bot: {e}")
            raise
    
    async def stop(self):
        if self.handler:
            await self.handler.close_async()
        self.logger.info("PantherBot stopped")

async def main():
    bot = PantherSlackBot()
    
    try:
        await bot.start()
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("\nShutting down PantherBot...")
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())

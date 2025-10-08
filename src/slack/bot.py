import os
import logging
import textwrap
from typing import Dict, Any, Optional
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))
from slackbot_config import load_slack_config

sys.path.append(str(Path(__file__).parent.parent))
from utils.config_loader import load_config

sys.path.append(str(Path(__file__).parent))
from slackbot_formatter import SlackFormatter
from slackbot_profile import ProfileHandler
from slackbot_handlers import MessageHandler


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
        self._rag_system = None
        
        from memory.student_profile import StudentProfileManager
        from memory.memory_interface import MemoryInterface
        
        self.student_manager = StudentProfileManager()
        self.memory_interface = MemoryInterface()
        
        self.formatter = SlackFormatter()
        self.profile_handler = ProfileHandler(self.student_manager, self.client)
        self.message_handler = MessageHandler(
            self._get_rag_system,
            self.student_manager, 
            self.formatter, 
            self.profile_handler,
            self.memory_interface
        )
        
        self._setup_handlers()
        
        self.handler = AsyncSocketModeHandler(self.app, self.slack_app_token)
        self.bot_user_id = None
        self.bot_info = None
        self._resources_ready = False

        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def _get_rag_system(self):
        """Lazily construct the RAG pipeline so heavy dependencies are only imported when needed."""
        if self._rag_system is None:
            from retrieval.unified_rag import UnifiedRAG
            self._rag_system = UnifiedRAG()
        return self._rag_system
    
    def _setup_handlers(self):
        
        @self.app.message("hello")
        async def handle_hello(message, say):
            await say(f"Hello <@{message['user']}>! I'm PantherBot, your academic advisor assistant. Ask me about course requirements, registration, or academic policies!")
        
        @self.app.message("help")
        async def handle_help(message, say):
            help_text = textwrap.dedent("""
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
            """).strip()
            await say(help_text)
        
        @self.app.event("app_mention")
        async def handle_mention(event, say):
            user_id = event['user']
            text = event['text']
            
            clean_text = self.message_handler.clean_mention_text(text, self.bot_user_id)
            
            if clean_text.strip():
                await self.message_handler.process_academic_query(clean_text, user_id, say)
            else:
                await say(f"Hi <@{user_id}>! What academic question can I help you with?")
        
        @self.app.message("")
        async def handle_direct_message(message, say):
            logging.info(f"Received message: {message}")
            
            if message.get('user') == self.bot_user_id:
                logging.info("Skipping message from bot itself")
                return
            
            text = message.get('text', '').strip()
            user_id = message['user']
            
            if not text:
                return
                
            if text.lower() in ['hello', 'help']:
                logging.info(f"Skipping hello/help message: {text}")
                return
            
            await self.message_handler.handle_user_message(text, user_id, say)

        @self.app.command("/clear_history")
        async def handle_clear_history_slash_command(ack, command, say):
            await ack()
            user_id = command['user_id']
            await self.message_handler.handle_clear_history_command(user_id, say)

        @self.app.command("/reset_profile")
        async def handle_reset_profile_slash_command(ack, command, say):
            await ack()
            user_id = command['user_id']
            await self.message_handler.handle_reset_profile_command(user_id, say)
    
    async def start(self):
        try:
            self.logger.info("Starting PantherBot Slack integration...")

            if not self._resources_ready:
                await self.student_manager.initialize()
                await self.memory_interface.initialize()
                self._resources_ready = True
            
            auth_response = await self.client.auth_test()
            self.bot_user_id = auth_response["user_id"]
            self.bot_info = auth_response
            
            self.logger.info(f"Bot authenticated as {auth_response['user']} (ID: {self.bot_user_id})")
            
            await self.handler.start_async()
            self.logger.info("PantherBot is now running and listening for messages!")
            
        except SlackApiError as e:
            self.logger.error(f"Slack API error during startup: {e.response['error']}")
            raise
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}")
            raise
    
    async def stop(self):
        try:
            self.logger.info("Stopping PantherBot...")
            await self.handler.close_async()
            if self._resources_ready:
                await self.student_manager.close()
                await self.memory_interface.close()
                self._resources_ready = False
            self.logger.info("PantherBot stopped successfully")
        except Exception as e:
            self.logger.error(f"Error stopping bot: {e}")


if __name__ == "__main__":
    import asyncio
    
    async def main():
        bot = PantherSlackBot()
        try:
            await bot.start()
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")
        finally:
            await bot.stop()
    
    asyncio.run(main())
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
from memory.student_profile import StudentProfileManager
from memory.memory_interface import MemoryInterface


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
        self.student_manager = StudentProfileManager()
        self.memory_interface = MemoryInterface()
        
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
            user_id = message['user']
            
            if not text:
                return
                
            if text.lower() in ['hello', 'help']:
                logging.info(f"Skipping hello/help message: {text}")
                return
            
            await self._handle_user_message(text, user_id, say)
    
    def _clean_mention_text(self, text: str) -> str:
        if self.bot_user_id:
            mention = f"<@{self.bot_user_id}>"
            text = text.replace(mention, "").strip()
        return text
    
    async def _handle_user_message(self, text: str, user_id: str, say):
        try:
            is_new = await self.student_manager.is_new_student(user_id)
            has_incomplete = await self.student_manager.has_incomplete_profile(user_id)
            
            if is_new or has_incomplete:
                major = self.student_manager.parse_major_input(text)
                catalog_year = self.student_manager.parse_catalog_year_input(text)
                
                if major or catalog_year:
                    await self._handle_profile_setup(text, user_id, say)
                elif is_new:
                    await self._initiate_profile_setup(user_id, say)
                else:
                    # Has incomplete profile but didn't provide recognizable input
                    existing_student = await self.student_manager.get_student_profile(user_id)
                    if existing_student.get('major') and not existing_student.get('catalog_year'):
                        await say("""I need your catalog year to complete your profile.

Your catalog year is the year you first entered the university.

Valid Catalog Years: 2022, 2023, 2024, 2025

Example: 2024""")
                    else:
                        await self._initiate_profile_setup(user_id, say)
                return
            
            if text.lower().startswith('update') or 'major:' in text.lower() or 'catalog year:' in text.lower():
                major = self.student_manager.parse_major_input(text)
                catalog_year = self.student_manager.parse_catalog_year_input(text)
                if major or catalog_year:
                    await self._handle_profile_update(text, user_id, say)
                    return
            
            await self._process_academic_query(text, user_id, say)
            
        except Exception as e:
            self.logger.error(f"Error handling user message: {e}")
            await say("Sorry, I encountered an error. Please try again.")

    async def _initiate_profile_setup(self, user_id: str, say):
        await say("Hello! This is the first time I'm chatting with you. I'm PantherBot, your academic advisor assistant.")
        
        await asyncio.sleep(1)
        
        await say("""
        To provide you with personalized academic guidance, I need to set up your student profile.
        First, please tell me your major by providing me with your major:
        Valid Majors:
        • Computer Science
        • Computer Engineering 
        • Data Science
        • Software Engineering
        • Electrical Engineering
        Example: Computer Science
        """)

    async def _handle_profile_setup(self, text: str, user_id: str, say):
        major = self.student_manager.parse_major_input(text)
        catalog_year = self.student_manager.parse_catalog_year_input(text)
        
        existing_student = await self.student_manager.get_student_profile(user_id)
        
        if existing_student and not existing_student.get('catalog_year') and catalog_year:
            success, message = await self.student_manager.complete_profile_with_catalog_year(user_id, text)
            if success:
                final_profile = await self.student_manager.get_student_profile(user_id)
                await say(f"Perfect! Your profile is now complete:\n• Major: *{final_profile['major']}*\n• Catalog Year: *{final_profile['catalog_year']}*\n\nYou can now ask me about course requirements, academic policies, and more!")
            else:
                await say(f"{message}")
            return
        
        if major and catalog_year:
            success, message = await self.student_manager.create_student_profile_from_text(user_id, text)
            if success:
                await say(f"Perfect! Your profile has been created:\n• Major: *{major}*\n• Catalog Year: *{catalog_year}*\n\nYou can now ask me about course requirements, academic policies, and more!")
            else:
                await say(f"{message}")
            return
            
        elif major and not catalog_year:
            success, message = await self.student_manager.create_student_profile_from_text(user_id, text)
            if success:
                await say(message)
                await asyncio.sleep(1)
                await say("""
                Now, please tell me your catalog year by providing me with your catalog year:

                Your catalog year is the year you first entered the university.

                Valid Catalog Years: 2022, 2023, 2024, 2025

                Example: 2024
            """)
            else:
                await say(f"{message}")
            return
            
        elif catalog_year and not major:
            await say("""
            Please provide your major first before setting your catalog year.

            Valid Majors:
            • Computer Science
            • Computer Engineering 
            • Data Science
            • Software Engineering
            • Electrical Engineering

            Example: Computer Science
                """)
            return
        else:
            await say("""
            I didn't recognize that format. Please provide your major like this:

            Computer Science

            Valid Majors:
            • Computer Science
            • Computer Engineering 
            • Data Science
            • Software Engineering
            • Electrical Engineering
                """)
            return

    async def _handle_partial_profile_setup(self, text: str, user_id: str, say):
        catalog_year = self.student_manager.parse_catalog_year_input(text)
        
        if catalog_year:
            existing_student = await self.student_manager.get_student_profile(user_id)
            if existing_student and existing_student.get('major'):
                success, message = await self.student_manager.update_student_profile(user_id, catalog_year=catalog_year)
                if success:
                    await say(f"Perfect! Your profile is now complete:\n• Major: *{existing_student['major']}*\n• Catalog Year: *{catalog_year}*\n\nYou can now ask me about course requirements, academic policies, and more!")
                else:
                    await say(f"{message}")
            else:
                await say("Please provide your major first before setting your catalog year.")
        else:
            await say("""
            I need your catalog year to complete your profile.

            Example: 2024
                    
            Valid Catalog Years: 2022, 2023, 2024, 2025
            """)

    async def _handle_profile_update(self, text: str, user_id: str, say):
        major = self.student_manager.parse_major_input(text)
        catalog_year = self.student_manager.parse_catalog_year_input(text)
        
        if major or catalog_year:
            success, message = await self.student_manager.update_student_profile(user_id, major=major, catalog_year=catalog_year)
            if success:
                profile = await self.student_manager.get_student_profile(user_id)
                await say(f"Profile updated!\n• Major: *{profile['major']}*\n• Catalog Year: *{profile['catalog_year']}*")
            else:
                await say(f"{message}")
        else:
            await say("Please specify what you'd like to update. Examples:\n• Major: Computer Science\n• Catalog Year: 2024")

    async def _process_academic_query(self, query: str, user_id: str, say):
        try:
            user_info = await self._get_user_context(user_id)
            
            if not user_info.get('program') or not user_info.get('year'):
                await say("I need your student profile to provide personalized guidance. Please set up your profile first.")
                return
            
            conversation_context = await self.memory_interface.get_recent_context(user_id)
            
            enhanced_query = query
            if conversation_context:
                enhanced_query = f"{conversation_context}\n\nCurrent question: {query}"
            
            await say("Let me look that up for you...")
            
            answer, retrieved_chunks = self.rag_system.answer_question(
                query=enhanced_query,
                student_program=user_info.get('program'),
                student_year=user_info.get('year'),
                top_k=self.config['retrieval']['top_k'],
                enable_reranking=False,
                use_streaming=False
            )
            
            formatted_response = self._format_response(answer, retrieved_chunks)
            await say(formatted_response)
            
            await self.memory_interface.add_conversation_turn(user_id, query, answer)
            
            self.logger.info(f"Processed query for user {user_id}: {query[:50]}...")
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            await say("Sorry, I encountered an error processing your question. Please try again or contact academic advising directly.")

    def _validate_user_access(self, user_id: str) -> bool:
        if not user_id or not isinstance(user_id, str):
            return False
        if not user_id.startswith('U') or len(user_id) < 9:
            return False
        return user_id.isalnum()

    async def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        if not self._validate_user_access(user_id):
            self.logger.warning(f"Invalid user access attempt: {user_id}")
            return {'program': None, 'year': None}
            
        try:
            student = await self.student_manager.get_student_profile(user_id)
            if student:
                return {
                    'program': student['major'],
                    'year': str(student['catalog_year']) if student['catalog_year'] else None
                }
        except Exception as e:
            self.logger.error(f"Error getting user context: {e}")
        
        return {
            'program': None,
            'year': None
        }
    
    def _convert_markdown_to_slack(self, text: str) -> str:
        """Convert Markdown formatting to Slack-compatible formatting"""
        import re
        
        # bold regex
        text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
        
        # bullet points regex
        text = re.sub(r'^(\s*)[*\-]\s+', r'\1• ', text, flags=re.MULTILINE)

        # numbered lists regex
        text = re.sub(r'^(\s*)(\d+)\.\s+', r'\1\2. ', text, flags=re.MULTILINE)

        # italic regex
        text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'_\1_', text)

        # headers regex
        text = re.sub(r'^#+\s*(.*?)$', r'*\1*', text, flags=re.MULTILINE)

        # whitespace cleanup regex
        text = re.sub(r'\n{3,}', '\n\n', text)

        # hyperlinks regex
        text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', text)
        
        return text
    
    def _format_response(self, response: str, sources: list) -> str:
        slack_formatted_response = self._convert_markdown_to_slack(response)
        
        formatted = f"*PantherBot Academic Assistant*\n\n{slack_formatted_response}"
        
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
            logging.info("Initializing database managers...")
            await self.student_manager.initialize()
            await self.memory_interface.initialize()
            
            logging.info("Testing Slack authentication...")
            auth_response = await self.client.auth_test()
            logging.info(f"Authentication successful! Bot: {auth_response['user']} on {auth_response['team']}")
            
            self.bot_user_id = auth_response['user_id']
            self.bot_info = auth_response
            
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
        
        await self.student_manager.close()
        await self.memory_interface.close()
        
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

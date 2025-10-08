import asyncio
import logging
import textwrap
from typing import Dict, Any, Callable

import sys
from pathlib import Path

src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))



class MessageHandler:
    
    def __init__(self, rag_provider: Callable[[], Any], student_manager, formatter, profile_handler, memory_interface=None):
        self._rag_provider = rag_provider
        self.student_manager = student_manager
        self.formatter = formatter
        self.profile_handler = profile_handler
        self.memory_interface = memory_interface
        self.logger = logging.getLogger(__name__)
    
    async def handle_user_message(self, text: str, user_id: str, say):
        try:
            is_new = await self.student_manager.is_new_student(user_id)
            has_incomplete = await self.student_manager.has_incomplete_profile(user_id)
            
            if is_new or has_incomplete:
                major = self.student_manager.parse_major_input(text)
                catalog_year = self.student_manager.parse_catalog_year_input(text)
                
                if major or catalog_year:
                    await self.profile_handler.handle_profile_setup(text, user_id, say)
                elif is_new:
                    await self.profile_handler.initiate_profile_setup(user_id, say)
                else:
                    await self.profile_handler.handle_partial_profile_setup(text, user_id, say)
                return
            
            profile = await self.student_manager.get_student_profile(user_id)
            if profile and not profile.get('additional_program_asked', False):
                if await self.profile_handler.handle_additional_program_type(text, user_id, say):
                    await self.student_manager.update_student_profile(user_id, additional_program_asked=True)
                    return
                elif await self.profile_handler.handle_additional_program_response(text, user_id, say):
                    await self.student_manager.update_student_profile(user_id, additional_program_asked=True)
                    return
            
          
            if profile and profile.get('additional_program_asked', False) and not profile.get('minor'):
                if await self.profile_handler.handle_additional_program_response(text, user_id, say):
                    return
            
            if text.lower().startswith('update') or 'major:' in text.lower() or 'catalog year:' in text.lower():
                major = self.student_manager.parse_major_input(text)
                catalog_year = self.student_manager.parse_catalog_year_input(text)
                if major or catalog_year:
                    await self.profile_handler.handle_profile_update(text, user_id, say)
                    return
            
            await self.process_academic_query(text, user_id, say)
            
        except Exception as e:
            self.logger.error(f"Error handling user message: {e}")
            await say("Sorry, I encountered an error. Please try again.")
    
    async def process_academic_query(self, query: str, user_id: str, say):
        try:
            if not self._validate_user_access(user_id):
                await say("Access denied. Please contact your administrator.")
                return
            
            context = await self._get_user_context(user_id)
            
            rag_system = self._rag_provider()
            answer, sources = await asyncio.to_thread(
                rag_system.answer_question,
                query,
                student_program=context.get('major'),
                student_year=context.get('catalog_year'),
                student_minor=context.get('minor'),
                use_streaming=False,
                return_debug_info=False
            )
            
            formatted_response = self.formatter.format_response(answer, sources)
            await say(formatted_response)
            
            if self.memory_interface:
                try:
                    await self.memory_interface.add_conversation_turn(user_id, query, answer)
                except Exception as e:
                    self.logger.error(f"Error saving conversation: {e}")
            
        except Exception as e:
            self.logger.error(f"Error processing query: {e}")
            error_response = "I encountered an error while processing your question. Please try rephrasing or ask something else."
            await say(error_response)
            
            if self.memory_interface:
                try:
                    await self.memory_interface.add_conversation_turn(user_id, query, error_response)
                except Exception as e:
                    self.logger.error(f"Error saving failed conversation: {e}")
    
    def _validate_user_access(self, user_id: str) -> bool:
        return True
    
    # Convert full minor name to the code expected by the RAG system
    def _convert_minor_to_code(self, minor_name: str) -> str:
        if not minor_name:
            return None
            
        minor_mappings = {
            "Analytics Minor": "analytics",
            "Computer Engineering Minor": "ce", 
            "Computer Science Minor": "cs",
            "Electrical Engineering Minor": "ee",
            "Game Development Programming Minor": "gamedev",
            "Information Security Policy Minor": "isp"
        }
        
        return minor_mappings.get(minor_name, minor_name.lower())
    
    async def _get_user_context(self, user_id: str) -> Dict[str, Any]:
        try:
            student_profile = await self.student_manager.get_student_profile(user_id)
            
            if not student_profile:
                return {}
            
            raw_minor = student_profile.get('minor')
            minor_code = self._convert_minor_to_code(raw_minor) if raw_minor else None
            
            context = {
                'major': student_profile.get('major'),
                'catalog_year': student_profile.get('catalog_year'),
                'minor': minor_code,
                'user_id': user_id
            }
            
            return context
            
        except Exception as e:
            self.logger.error(f"Error getting user context: {e}")
            return {}

    async def handle_clear_history_command(self, user_id: str, say):
        try:
            success, message = await self.student_manager.clear_user_history(user_id)
            await say(message)
        except Exception as e:
            self.logger.error(f"Error handling clear history command: {e}")
            await say("Sorry, I encountered an error while clearing your history. Please try again.")

    async def handle_reset_profile_command(self, user_id: str, say):
        try:
            success, message = await self.student_manager.reset_user_profile(user_id)
            await say(message)
        except Exception as e:
            self.logger.error(f"Error handling reset profile command: {e}")
            await say("Sorry, I encountered an error while resetting your profile. Please try again.")
    
    def clean_mention_text(self, text: str, bot_user_id: str) -> str:
        if bot_user_id:
            mention = f"<@{bot_user_id}>"
            text = text.replace(mention, "").strip()
        return text
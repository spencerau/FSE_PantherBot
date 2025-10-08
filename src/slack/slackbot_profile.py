import asyncio
import textwrap
from typing import Dict, Any, Optional, Tuple

import sys
from pathlib import Path

src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))



class ProfileHandler:
    
    def __init__(self, student_manager, slack_client=None):
        self.student_manager = student_manager
        self.slack_client = slack_client
        
        self.major_options = {
            '1': 'Computer Science',
            '2': 'Computer Engineering',
            '3': 'Data Science', 
            '4': 'Software Engineering',
            '5': 'Electrical Engineering'
        }
        
        self.minor_options = {
            '1': 'Analytics Minor',
            '2': 'Computer Engineering Minor',
            '3': 'Computer Science Minor',
            '4': 'Electrical Engineering Minor',
            '5': 'Game Development Programming Minor',
            '6': 'Information Security Policy Minor'
        }
        
        self.additional_program_options = {
            '1': 'minor',
            '2': 'none'
            # '2': 'double_major',  # TODO: Implement double major support
            # '3': 'themed_inquiry',  # TODO: Implement themed inquiry support
        }
        
        # TODO: Uncomment when implementing themed inquiry support
        # self.themed_inquiry_options = {
        #     '1': 'Artificial Intelligence',
        #     '2': 'Cybersecurity',
        #     '3': 'Sustainable Technology',
        #     '4': 'Entrepreneurship',
        #     '5': 'Other'
        # }
    
    async def initiate_profile_setup(self, user_id: str, say):
        await self._fetch_and_store_user_name(user_id)
        
        await say("Hello! This is the first time I'm chatting with you. I'm PantherBot, your academic advisor assistant.")
        await asyncio.sleep(1)
        
        await say(textwrap.dedent("""
            To provide you with personalized academic guidance, I need to set up your student profile.

            First, please tell me your major:

            Valid Majors:
            1. Computer Science
            2. Computer Engineering 
            3. Data Science
            4. Software Engineering
            5. Electrical Engineering

            Example: Enter '1' for Computer Science
        """).strip())
    
    async def handle_profile_setup(self, text: str, user_id: str, say):
        major = self.student_manager.parse_major_input(text)
        catalog_year = self.student_manager.parse_catalog_year_input(text)
        
        existing_student = await self.student_manager.get_student_profile(user_id)
        
        if existing_student and not existing_student.get('catalog_year') and catalog_year:
            success, message = await self.student_manager.complete_profile_with_catalog_year(user_id, text)
            if success:
                final_profile = await self.student_manager.get_student_profile(user_id)
                await self._ask_about_additional_programs(user_id, say, final_profile)
            else:
                await say(f"{message}")
            return
        
        if major and catalog_year:
            success, message = await self.student_manager.create_student_profile_from_text(user_id, text)
            if success:
                profile = await self.student_manager.get_student_profile(user_id)
                await self._ask_about_additional_programs(user_id, say, profile)
            else:
                await say(f"{message}")
            return
        
        if major:
            success, message = await self.student_manager.create_student_profile_from_text(user_id, text)
            if success:
                await say(textwrap.dedent(f"""
                    Great! I've recorded your major as *{major}*.

                    Now I need your catalog year. This is the year you first entered the university.

                    Valid Catalog Years: 2022, 2023, 2024, 2025

                    Example: 2024
                """).strip())
            else:
                await say(f"{message}")
        else:
            await say(textwrap.dedent("""
                Please provide your major.

                Valid Majors:
                1. Computer Science
                2. Computer Engineering 
                3. Data Science
                4. Software Engineering
                5. Electrical Engineering

                Example: Enter '1' for Computer Science
            """).strip())
    
    async def _ask_about_additional_programs(self, user_id: str, say, profile: Dict[str, Any]):
        await say(textwrap.dedent(f"""
            Perfect! Your profile has been created:
            Major: *{profile['major']}*
            Catalog Year: *{profile['catalog_year']}*

            Are you also pursuing a minor?
            1. Yes, I'm pursuing a minor
            2. No, just my primary major

            Example: Enter '1' for Yes or '2' for No
        """).strip())
    
    async def handle_additional_program_type(self, text: str, user_id: str, say) -> bool:
        text_stripped = text.strip()
        
        if text_stripped in self.additional_program_options:
            program_type = self.additional_program_options[text_stripped]
            
            if program_type == 'minor':
                await self._ask_for_minor(user_id, say)
                return True
            elif program_type == 'none':
                await say("Great! Your profile is complete. You can now ask me about course requirements, academic policies, and more!")
                return True
            # TODO: Uncomment when implementing these features
            # elif program_type == 'double_major':
            #     await self._ask_for_double_major(user_id, say)
            #     return True
            # elif program_type == 'themed_inquiry':
            #     await self._ask_for_themed_inquiry(user_id, say)
            #     return True
        
        text_lower = text.lower().strip()
        if 'minor' in text_lower or 'yes' in text_lower:
            await self._ask_for_minor(user_id, say)
            return True
        elif 'none' in text_lower or 'no' in text_lower:
            await say("Great! Your profile is complete. You can now ask me about course requirements, academic policies, and more!")
            return True
        # TODO: Uncomment when implementing these features
        # elif 'double major' in text_lower or 'double' in text_lower:
        #     await self._ask_for_double_major(user_id, say)
        #     return True
        # elif 'themed inquiry' in text_lower or 'themed' in text_lower or 'inquiry' in text_lower or 'ti' in text_lower:
        #     await self._ask_for_themed_inquiry(user_id, say)
        #     return True
        
        return False
    
    async def _ask_for_minor(self, user_id: str, say):
        await say(textwrap.dedent("""
            What minor are you pursuing?

            Available Minors:
            1. Analytics Minor
            2. Computer Engineering Minor
            3. Computer Science Minor
            4. Electrical Engineering Minor
            5. Game Development Programming Minor
            6. Information Security Policy Minor

            Example: Select '3' for the Computer Science Minor
        """).strip())
    
    # TODO: Implement double major support
    # async def _ask_for_double_major(self, user_id: str, say):
    #     await say(textwrap.dedent("""
    #         What is your second major?

    #         Valid Second Majors:
    #         1. Computer Science
    #         2. Computer Engineering
    #         3. Data Science
    #         4. Software Engineering
    #         5. Electrical Engineering

    #         Example: Enter '3' for Data Science
    #     """).strip())
    
    # TODO: Implement themed inquiry support
    # async def _ask_for_themed_inquiry(self, user_id: str, say):
    #     await say(textwrap.dedent("""
    #         What themed inquiry are you pursuing?

    #         Available Themed Inquiries:
    #         1. Artificial Intelligence
    #         2. Cybersecurity
    #         3. Sustainable Technology
    #         4. Entrepreneurship
    #         5. Other (please specify)

    #         Example: Enter '1' for Artificial Intelligence
    #     """).strip())
    
    async def handle_additional_program_response(self, text: str, user_id: str, say) -> bool:
        text_stripped = text.strip()
        
        if text_stripped in self.minor_options:
            program_name = self.minor_options[text_stripped]
            await self._save_additional_program(user_id, 'minor', program_name, say)
            return True
        
        # TODO: Uncomment when implementing these features
        # elif text_stripped in self.major_options:
        #     program_name = self.major_options[text_stripped]
        #     await self._save_additional_program(user_id, 'double_major', program_name, say)
        #     return True
        # elif text_stripped in self.themed_inquiry_options:
        #     if text_stripped == '5':
        #         await say("Please specify your themed inquiry:")
        #         return True
        #     else:
        #         program_name = self.themed_inquiry_options[text_stripped]
        #         await self._save_additional_program(user_id, 'themed_inquiry', program_name, say)
        #         return True
        
        # Only match specific minor keywords when they are standalone selections, not questions
        minor_keywords = ['cs minor', 'data science minor', 'analytics minor', 'game development minor', 'security minor', 'computer science minor']
        
        text_lower = text.lower().strip()
        
        # Avoid matching questions about minors (e.g., "what about my minor")
        question_indicators = ['what', 'about', 'my', 'tell me', 'explain', '?']
        is_question = any(indicator in text_lower for indicator in question_indicators)
        
        if not is_question and any(keyword in text_lower for keyword in minor_keywords):
            await self._save_additional_program(user_id, 'minor', text, say)
            return True
        
        # TODO: Uncomment when implementing these features
        # elif any(keyword in text_lower for major_keywords):
        #     await self._save_additional_program(user_id, 'double_major', text, say)
        #     return True
        # elif len(text.split()) <= 4:
        #     await self._save_additional_program(user_id, 'themed_inquiry', text, say)
        #     return True
        
        return False
    
    async def _save_additional_program(self, user_id: str, program_type: str, program_name: str, say):
        program_display = program_name.title()
        type_display = program_type.replace('_', ' ').title()
        
        if program_type == 'minor':
            success, message = await self.student_manager.update_student_profile(
                user_id, 
                minor=program_name,
                additional_program_asked=True
            )
            if not success:
                await say(f"Error saving your {type_display}: {message}")
                return
        
        profile = await self.student_manager.get_student_profile(user_id)
        await say(textwrap.dedent(f"""
            Excellent! I've added your {type_display}: *{program_display}*

            Your complete profile:
            Major: *{profile['major']}*
            Catalog Year: *{profile['catalog_year']}*
            {type_display}: *{program_display}*

            You can now ask me about course requirements, academic policies, and more!
        """).strip())
    
    async def handle_partial_profile_setup(self, text: str, user_id: str, say):
        catalog_year = self.student_manager.parse_catalog_year_input(text)
        
        if catalog_year:
            existing_student = await self.student_manager.get_student_profile(user_id)
            if existing_student and existing_student.get('major'):
                success, message = await self.student_manager.update_student_profile(user_id, catalog_year=catalog_year)
                if success:
                    await self._ask_about_additional_programs(user_id, say, {**existing_student, 'catalog_year': catalog_year})
                else:
                    await say(f"{message}")
            else:
                await say("Please provide your major first before setting your catalog year.")
        else:
            await say(textwrap.dedent("""
                I need your catalog year to complete your profile.

                Example: 2024
                        
                Valid Catalog Years: 2022, 2023, 2024, 2025
            """).strip())
    
    async def handle_profile_update(self, text: str, user_id: str, say):
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
            await say("Please specify what you'd like to update. Use format like 'Major: Computer Science' or 'Catalog Year: 2024'")

    async def _fetch_and_store_user_name(self, user_id: str):
        if not self.slack_client:
            return
            
        try:
            response = await self.slack_client.users_info(user=user_id)
            if response['ok']:
                user_info = response['user']
                await self.student_manager.create_user_name_from_slack(user_id, user_info)
        except Exception as e:
            print(f"Warning: Could not fetch user name for {user_id}: {e}")
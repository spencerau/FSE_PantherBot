import asyncio
from typing import Dict, Optional, Tuple
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
from memory.database import DatabaseManager

logger = logging.getLogger(__name__)

class StudentProfileManager:
    def __init__(self):
        env_path = Path(__file__).parent / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            
        self.db_manager = DatabaseManager()
        self.valid_majors = [
            "Computer Science", "Computer Engineering", "Data Science", 
            "Software Engineering", "Electrical Engineering"
        ]
        self.major_mappings = {
            "computer science": "Computer Science",
            "cs": "Computer Science",
            "comp sci": "Computer Science",
            "computer engineering": "Computer Engineering", 
            "ce": "Computer Engineering",
            "comp eng": "Computer Engineering",
            "data science": "Data Science",
            "ds": "Data Science",
            "software engineering": "Software Engineering",
            "se": "Software Engineering",
            "soft eng": "Software Engineering",
            "electrical engineering": "Electrical Engineering",
            "ee": "Electrical Engineering",
            "elec eng": "Electrical Engineering"
        }
        self.valid_catalog_years = [2022, 2023, 2024, 2025]

    async def initialize(self):
        await self.db_manager.initialize()

    def parse_major_input(self, text: str) -> Optional[str]:
        """Parse major from flexible user input"""
        if "major:" in text.lower():
            major_text = re.split(r'major:\s*', text, flags=re.IGNORECASE)[1].strip()
        else:
            major_text = text.strip()
        
        major_text = re.sub(r',\s*\d{4}.*$', '', major_text)
        major_text = re.sub(r'\s*\d{4}.*$', '', major_text)
        
        normalized = major_text.lower().strip()
        
        if normalized in self.major_mappings:
            return self.major_mappings[normalized]
        
        for valid_major in self.valid_majors:
            if normalized == valid_major.lower():
                return valid_major
        
        return None

    def parse_catalog_year_input(self, text: str) -> Optional[int]:
        if "catalog year:" in text.lower() or "year:" in text.lower():
            year_text = re.split(r'(?:catalog\s+)?year:\s*', text, flags=re.IGNORECASE)[-1].strip()
        else:
            year_text = text.strip()
        
        year_match = re.search(r'\b(20\d{2})\b', year_text)
        if year_match:
            year = int(year_match.group(1))
            if year in self.valid_catalog_years:
                return year
        
        return None

    def parse_profile_input(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        major = self.parse_major_input(text)
        catalog_year = self.parse_catalog_year_input(text)
        return major, catalog_year

    async def get_student_profile(self, slack_user_id: str) -> Optional[Dict]:
        return await self.db_manager.get_student(slack_user_id)

    async def is_new_student(self, slack_user_id: str) -> bool:
        student = await self.get_student_profile(slack_user_id)
        return student is None

    async def has_incomplete_profile(self, slack_user_id: str) -> bool:
        student = await self.get_student_profile(slack_user_id)
        if student is None:
            return False
        return student.get('major') is None or student.get('catalog_year') is None

    async def create_student_profile(self, slack_user_id: str, major: str, catalog_year: int) -> Tuple[bool, str]:
        if isinstance(major, str):
            parsed_major = self.parse_major_input(major)
            if parsed_major:
                major = parsed_major
        
        if major not in self.valid_majors:
            return False, f"Invalid major. Valid options: {', '.join(self.valid_majors)}"
        
        if catalog_year not in self.valid_catalog_years:
            return False, f"Invalid catalog year. Valid options: {', '.join(map(str, self.valid_catalog_years))}"
        
        success = await self.db_manager.create_student(slack_user_id, major, catalog_year)
        if success:
            return True, "Profile created successfully!"
        else:
            return False, "Error creating profile. Please try again."

    async def create_student_profile_from_text(self, slack_user_id: str, text: str) -> Tuple[bool, str]:
        """Create profile from flexible text input like 'Computer Science' or 'Major: Computer Science'"""
        major, catalog_year = self.parse_profile_input(text)
        
        if major and catalog_year:
            # Both provided - create complete profile
            return await self.create_student_profile(slack_user_id, major, catalog_year)
        elif major and not catalog_year:
            # Only major provided - create partial profile
            success = await self.db_manager.create_student(slack_user_id, major=major)
            if success:
                return True, f"Great! I've noted your major as *{major}*. Now I need your catalog year."
            else:
                return False, "Error saving your major. Please try again."
        elif catalog_year and not major:
            return False, "Please provide your major first before setting your catalog year."
        else:
            return False, (
                "I couldn't understand your input. Please specify your major like this:\n"
                f"• {chr(10).join(['Major: ' + m for m in self.valid_majors])}\n\n"
                "Example: Major: Computer Science"
            )

    async def complete_profile_with_catalog_year(self, slack_user_id: str, text: str) -> Tuple[bool, str]:
        """Complete an existing partial profile with catalog year"""
        catalog_year = self.parse_catalog_year_input(text)
        
        if not catalog_year:
            return False, (
                "I couldn't find a valid catalog year. Please specify one of:\n"
                f"• {', '.join(map(str, self.valid_catalog_years))}\n\n"
                "Example: Catalog Year: 2024"
            )
        
        success = await self.db_manager.update_student(slack_user_id, catalog_year=catalog_year)
        if success:
            return True, f"Perfect! Your catalog year has been set to *{catalog_year}*."
        else:
            return False, "Error updating your catalog year. Please try again."

    async def update_student_profile(self, slack_user_id: str, major: str = None, catalog_year: int = None) -> Tuple[bool, str]:
        if isinstance(major, str):
            parsed_major = self.parse_major_input(major)
            if parsed_major:
                major = parsed_major
        
        if major and major not in self.valid_majors:
            return False, f"Invalid major. Valid options: {', '.join(self.valid_majors)}"
        
        if catalog_year and catalog_year not in self.valid_catalog_years:
            return False, f"Invalid catalog year. Valid options: {', '.join(map(str, self.valid_catalog_years))}"
        
        success = await self.db_manager.update_student(slack_user_id, major, catalog_year)
        if success:
            return True, "Profile updated successfully!"
        else:
            return False, "Error updating profile. Please try again."

    def get_valid_majors(self) -> list:
        return self.valid_majors.copy()

    def get_valid_catalog_years(self) -> list:
        return self.valid_catalog_years.copy()

    async def close(self):
        await self.db_manager.close()

import asyncio
import re
import logging
from typing import Dict, Optional, Tuple

from memory.fse_profile import (
    get_student_profile,
    upsert_student_profile,
    clear_user_sessions,
    delete_student_profile,
)

logger = logging.getLogger(__name__)


class FSEStudentManager:

    VALID_MAJORS = [
        "Computer Science",
        "Computer Engineering",
        "Data Science",
        "Software Engineering",
        "Electrical Engineering",
    ]
    _MAJOR_MAP = {
        "cs": "Computer Science",
        "ce": "Computer Engineering",
        "ds": "Data Science",
        "se": "Software Engineering",
        "ee": "Electrical Engineering",
        "1": "Computer Science",
        "2": "Computer Engineering",
        "3": "Data Science",
        "4": "Software Engineering",
        "5": "Electrical Engineering",
    }
    VALID_CATALOG_YEARS = [2022, 2023, 2024, 2025]

    def __init__(self, config: dict = None):
        self.config = config

    async def initialize(self):
        pass

    async def close(self):
        pass

    async def get_student_profile(self, user_id: str) -> Optional[Dict]:
        return await asyncio.to_thread(get_student_profile, user_id, self.config)

    async def is_new_student(self, user_id: str) -> bool:
        profile = await self.get_student_profile(user_id)
        return profile is None

    async def has_incomplete_profile(self, user_id: str) -> bool:
        profile = await self.get_student_profile(user_id)
        if profile is None:
            return False
        return profile.get('major') is None or profile.get('catalog_year') is None

    async def create_student_profile(
        self, user_id: str, major: str, catalog_year: int
    ) -> Tuple[bool, str]:
        parsed = self.parse_major_input(major)
        if parsed:
            major = parsed
        if major not in self.VALID_MAJORS:
            return False, f"Invalid major. Valid options: {', '.join(self.VALID_MAJORS)}"
        if catalog_year not in self.VALID_CATALOG_YEARS:
            return False, f"Invalid catalog year. Valid options: {', '.join(map(str, self.VALID_CATALOG_YEARS))}"
        await asyncio.to_thread(
            upsert_student_profile, user_id, major, catalog_year, None, False, self.config
        )
        return True, "Profile created successfully!"

    async def create_student_profile_from_text(
        self, user_id: str, text: str
    ) -> Tuple[bool, str]:
        major = self.parse_major_input(text)
        catalog_year = self.parse_catalog_year_input(text)

        if major and catalog_year:
            return await self.create_student_profile(user_id, major, catalog_year)
        elif major:
            await asyncio.to_thread(
                upsert_student_profile, user_id, major, None, None, None, self.config
            )
            return True, f"Great! I've noted your major as *{major}*. Now I need your catalog year."
        elif catalog_year:
            return False, "Please provide your major first before setting your catalog year."
        else:
            options = "\n".join(f"• Major: {m}" for m in self.VALID_MAJORS)
            return False, (
                f"I couldn't understand your input. Please specify your major:\n"
                f"{options}\n\nExample: Major: Computer Science"
            )

    async def complete_profile_with_catalog_year(
        self, user_id: str, text: str
    ) -> Tuple[bool, str]:
        catalog_year = self.parse_catalog_year_input(text)
        if not catalog_year:
            years = ', '.join(map(str, self.VALID_CATALOG_YEARS))
            return False, f"I couldn't find a valid catalog year. Valid options: {years}"
        await asyncio.to_thread(
            upsert_student_profile, user_id, None, catalog_year, None, None, self.config
        )
        return True, f"Perfect! Your catalog year has been set to *{catalog_year}*."

    async def update_student_profile(
        self,
        user_id: str,
        major: str = None,
        catalog_year: int = None,
        **kwargs,
    ) -> Tuple[bool, str]:
        if major:
            parsed = self.parse_major_input(major)
            if parsed:
                major = parsed
            if major not in self.VALID_MAJORS:
                return False, f"Invalid major. Valid options: {', '.join(self.VALID_MAJORS)}"
        if catalog_year and catalog_year not in self.VALID_CATALOG_YEARS:
            return False, f"Invalid catalog year. Valid options: {', '.join(map(str, self.VALID_CATALOG_YEARS))}"
        minor = kwargs.get('minor')
        additional_program_asked = kwargs.get('additional_program_asked')
        await asyncio.to_thread(
            upsert_student_profile,
            user_id, major, catalog_year, minor, additional_program_asked, self.config,
        )
        return True, "Profile updated successfully!"

    async def clear_user_history(self, user_id: str) -> Tuple[bool, str]:
        try:
            await asyncio.to_thread(clear_user_sessions, user_id, self.config)
            return True, "Your conversation history has been cleared successfully!"
        except Exception as e:
            logger.error("Error clearing history for %s: %s", user_id[:3], e)
            return False, "Error clearing your history. Please try again."

    async def reset_user_profile(self, user_id: str) -> Tuple[bool, str]:
        try:
            await asyncio.to_thread(delete_student_profile, user_id, self.config)
            return True, "Your profile and all associated data has been deleted. You can start fresh by chatting with me again!"
        except Exception as e:
            logger.error("Error resetting profile for %s: %s", user_id[:3], e)
            return False, "An error occurred while deleting your profile."

    async def create_user_name_from_slack(self, user_id: str, user_info: Dict) -> bool:
        return True

    def parse_major_input(self, text: str) -> Optional[str]:
        if "major:" in text.lower():
            major_text = re.split(r'major:\s*', text, flags=re.IGNORECASE)[1].strip()
        else:
            major_text = text.strip()
        major_text = re.sub(r',\s*\d{4}.*$', '', major_text)
        major_text = re.sub(r'\s*\d{4}.*$', '', major_text)
        normalized = major_text.lower().strip()
        if normalized in self._MAJOR_MAP:
            return self._MAJOR_MAP[normalized]
        for valid in self.VALID_MAJORS:
            if normalized == valid.lower():
                return valid
        return None

    def parse_catalog_year_input(self, text: str) -> Optional[int]:
        if "catalog year:" in text.lower() or "year:" in text.lower():
            year_text = re.split(r'(?:catalog\s+)?year:\s*', text, flags=re.IGNORECASE)[-1].strip()
        else:
            year_text = text.strip()
        m = re.search(r'\b(20\d{2})\b', year_text)
        if m:
            year = int(m.group(1))
            if year in self.VALID_CATALOG_YEARS:
                return year
        return None

    def parse_profile_input(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        return self.parse_major_input(text), self.parse_catalog_year_input(text)

    def get_valid_majors(self) -> list:
        return self.VALID_MAJORS.copy()

    def get_valid_catalog_years(self) -> list:
        return self.VALID_CATALOG_YEARS.copy()

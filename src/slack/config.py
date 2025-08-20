"""
Slack Bot Configuration
Environment setup and configuration management for the Slack integration.
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

@dataclass
class SlackConfig:
    bot_token: str
    app_token: str
    signing_secret: str
    test_channel: Optional[str] = None
    test_user: Optional[str] = None
    debug_mode: bool = False
    student_major: Optional[str] = None
    student_catalog_year: Optional[str] = None

def load_slack_config() -> SlackConfig:
    
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    app_token = os.getenv("SLACK_APP_TOKEN") 
    signing_secret = os.getenv("SLACK_SIGNING_SECRET")
    
    if not bot_token:
        raise ValueError("SLACK_BOT_TOKEN environment variable is required")
    if not app_token:
        raise ValueError("SLACK_APP_TOKEN environment variable is required")
    if not signing_secret:
        raise ValueError("SLACK_SIGNING_SECRET environment variable is required")
    
    test_channel = os.getenv("SLACK_TEST_CHANNEL")
    test_user = os.getenv("SLACK_TEST_USER")
    debug_mode = os.getenv("SLACK_DEBUG", "false").lower() == "true"
    
    student_major = os.getenv("STUDENT_MAJOR")
    student_catalog_year = os.getenv("STUDENT_CATALOG_YEAR")
    
    return SlackConfig(
        bot_token=bot_token,
        app_token=app_token,
        signing_secret=signing_secret,
        test_channel=test_channel,
        test_user=test_user,
        debug_mode=debug_mode,
        student_major=student_major,
        student_catalog_year=student_catalog_year
    )

def validate_environment() -> bool:
    required_vars = [
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN", 
        "SLACK_SIGNING_SECRET"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables before running the Slack bot.")
        return False
    
    print("All required Slack environment variables are set")
    return True

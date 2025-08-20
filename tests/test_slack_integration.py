"""
Slack Integration Tests
Comprehensive pytest-based test suite for the PantherBot Slack integration.
"""

import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

env_path = Path(__file__).parent.parent / 'src' / 'slack' / '.env'
if env_path.exists():
    load_dotenv(env_path)


class TestSlackEnvironment:
    """Test environment setup and configuration."""
    
    def test_dependencies_installed(self):
        """Test that required packages are installed."""
        required_packages = ['slack_bolt', 'slack_sdk', 'aiohttp', 'dotenv']
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                pytest.fail(f"Required package '{package}' is not installed")
    
    def test_environment_variables_format(self):
        """Test that environment variables have correct format if set."""
        bot_token = os.getenv('SLACK_BOT_TOKEN')
        app_token = os.getenv('SLACK_APP_TOKEN')
        
        if bot_token and not bot_token.startswith('your-'):
            assert bot_token.startswith('xoxb-'), "SLACK_BOT_TOKEN should start with 'xoxb-'"
        
        if app_token and not app_token.startswith('your-'):
            assert app_token.startswith('xapp-'), "SLACK_APP_TOKEN should start with 'xapp-'"
    
    def test_config_module_import(self):
        """Test that slack config module can be imported."""
        try:
            from slack.config import load_slack_config, SlackConfig
            assert callable(load_slack_config)
            assert SlackConfig is not None
        except ImportError as e:
            pytest.fail(f"Failed to import slack config: {e}")


class TestSlackBot:
    """Test Slack bot functionality with mocked dependencies."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies for testing."""
        with patch('slack.bot.RAGAgent') as mock_rag, \
             patch('slack.bot.load_config') as mock_config, \
             patch('slack.bot.AsyncApp') as mock_app, \
             patch('slack.bot.AsyncWebClient') as mock_client, \
             patch('slack.bot.AsyncSocketModeHandler') as mock_handler:
            
            mock_config.return_value = {'test': 'config'}
            mock_rag_instance = MagicMock()
            mock_rag_instance.answer.return_value = {
                'response': 'Test response',
                'sources': []
            }
            mock_rag.return_value = mock_rag_instance
            
            yield {
                'rag': mock_rag,
                'config': mock_config,
                'app': mock_app,
                'client': mock_client,
                'handler': mock_handler
            }
    
    def test_bot_module_import(self):
        """Test that bot module can be imported."""
        try:
            from slack.bot import PantherSlackBot
            assert PantherSlackBot is not None
        except ImportError as e:
            pytest.fail(f"Failed to import PantherSlackBot: {e}")
    
    def test_bot_initialization_with_tokens(self, mock_dependencies):
        """Test that the bot initializes properly with valid tokens."""
        from slack.bot import PantherSlackBot
        
        bot = PantherSlackBot(
            slack_bot_token='xoxb-test-token',
            slack_app_token='xapp-test-token'
        )
        
        assert bot.slack_bot_token == 'xoxb-test-token'
        assert bot.slack_app_token == 'xapp-test-token'
        mock_dependencies['rag'].assert_called_once()
    
    def test_bot_missing_tokens_error(self):
        """Test that bot raises error with missing tokens."""
        from slack.bot import PantherSlackBot
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Missing required Slack tokens"):
                PantherSlackBot()


@pytest.mark.integration
class TestSlackLiveIntegration:
    """Live integration tests - requires actual Slack tokens."""
    
    @pytest.fixture
    def skip_if_no_tokens(self):
        """Skip test if tokens are not configured."""
        required_vars = ["SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"]
        missing = [var for var in required_vars if not os.getenv(var) or os.getenv(var).startswith('your-')]
        
        if missing:
            pytest.skip(f"Slack tokens not configured: {missing}")
    
    @pytest.mark.asyncio
    async def test_auth_connection(self, skip_if_no_tokens):
        """Test that the bot can authenticate with Slack."""
        from slack_sdk.web.async_client import AsyncWebClient
        
        client = AsyncWebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        
        try:
            response = await client.auth_test()
            assert response['ok'] is True
            assert 'user' in response
            assert 'team' in response
            print(f"Bot authenticated as: {response['user']} on {response['team']}")
            
        except Exception as e:
            pytest.fail(f"Authentication failed: {e}")
    
    @pytest.mark.asyncio
    async def test_channels_list(self, skip_if_no_tokens):
        """Test that the bot can list channels."""
        from slack_sdk.web.async_client import AsyncWebClient
        
        client = AsyncWebClient(token=os.getenv('SLACK_BOT_TOKEN'))
        
        try:
            response = await client.conversations_list(types="public_channel,private_channel")
            assert response['ok'] is True
            assert 'channels' in response
            print(f"Found {len(response['channels'])} channels")
            
        except Exception as e:
            pytest.fail(f"Channels list failed: {e}")


def test_integration_status():
    """Display current integration status."""
    print("\n" + "="*50)
    print("PantherBot Slack Integration Status")
    print("="*50)
    
    deps_ok = True
    required_packages = ['slack_bolt', 'slack_sdk', 'aiohttp', 'dotenv']
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            deps_ok = False
            break
    
    bot_token = os.getenv('SLACK_BOT_TOKEN')
    app_token = os.getenv('SLACK_APP_TOKEN')
    signing_secret = os.getenv('SLACK_SIGNING_SECRET')
    
    tokens_configured = all([
        bot_token and not bot_token.startswith('your-'),
        app_token and not app_token.startswith('your-'),
        signing_secret and not signing_secret.startswith('your-')
    ])
    
    print(f"Dependencies: {'INSTALLED' if deps_ok else '❌ MISSING'}")
    print(f"Tokens: {'CONFIGURED' if tokens_configured else '❌ NEED SETUP'}")
    
    if deps_ok and tokens_configured:
        print("\nReady for live testing!")
        print("   Run: pytest tests/test_slack_integration.py::TestSlackLiveIntegration -v")
        print("   Start bot: python src/slack/bot.py")
    else:
        print("\nSetup needed:")
        if not deps_ok:
            print("   pip install slack-bolt slack-sdk aiohttp python-dotenv")
        if not tokens_configured:
            print("   Add real tokens to src/slack/.env")
    
    print("="*50)


if __name__ == "__main__":
    test_integration_status()

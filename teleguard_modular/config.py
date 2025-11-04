"""Configuration loader"""
import os
from pathlib import Path
from dotenv import load_dotenv

def load_config():
    """Load configuration from environment"""
    env_path = Path(__file__).parent.parent / 'config' / '.env'
    load_dotenv(env_path)
    
    return {
        'api_id': int(os.getenv('API_ID', 0)),
        'api_hash': os.getenv('API_HASH', ''),
        'bot_token': os.getenv('BOT_TOKEN', ''),
        'admin_ids': [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x],
        'mongodb_uri': os.getenv('MONGO_URI', 'mongodb://localhost:27017/teleguard'),
    }

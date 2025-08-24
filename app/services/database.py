from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class MongoDB:
    client: AsyncIOMotorClient = None
    database = None

mongodb = MongoDB()

async def connect_to_mongo():
    """Create database connection"""
    try:
        mongodb.client = AsyncIOMotorClient(settings.mongodb_url)
        mongodb.database = mongodb.client[settings.database_name]
        
        # Create unique index on username
        await mongodb.database[settings.users_collection].create_index(
            "username", unique=True
        )
    
        logger.info("Connected to MongoDB")
        return mongodb.database
    except Exception as e:
        logger.error(f"Could not connect to MongoDB: {e}")
        raise

async def close_mongo_connection():
    """Close database connection"""
    if mongodb.client:
        mongodb.client.close()
        logger.info("Disconnected from MongoDB")

async def get_database():
    """Get database instance"""
    return mongodb.database

# User operations
async def get_user_by_username(username: str):
    """Get user by username"""
    collection = mongodb.database[settings.users_collection]
    user = await collection.find_one({"username": username})
    return user

async def create_user(user_data: dict):
    """Create new user"""
    collection = mongodb.database[settings.users_collection]
    try:
        result = await collection.insert_one(user_data)
        return result.inserted_id
    except DuplicateKeyError:
        raise ValueError("Username already exists")

async def get_all_users():
    """Get all users"""
    collection = mongodb.database[settings.users_collection]
    cursor = collection.find({}, {"password": 0})  # Exclude password field
    users = await cursor.to_list(length=None)
    return users

async def update_user_password(username: str, hashed_password: str):
    """Update user password"""
    collection = mongodb.database[settings.users_collection]
    result = await collection.update_one(
        {"username": username},
        {"$set": {"password": hashed_password}}
    )
    return result.modified_count > 0

async def delete_user(username: str):
    """Delete user"""
    collection = mongodb.database[settings.users_collection]
    result = await collection.delete_one({"username": username})
    return result.deleted_count > 0

from datetime import datetime
import traceback
from typing import Union


async def upsert_message_in_session(session_id: str, message: Union[str, dict, list], msg_type: str):
    """
    Inserts a new session if it doesn't exist, or appends a message if it does.
    
    Args:
        session_id (str): Unique session ID.
        message (str | dict | list): The user's or assistant's message.
        msg_type (str): Type of message (e.g., 'user', 'assistant').
    """
    try:
        chat_collection = mongodb.database[settings.users_chat_collection]

        existing_session = await chat_collection.find_one({"sessionId": session_id})

        if isinstance(message, dict):
            message_str = message
            message_str_only = message.get("project_planner_output", message)

        elif isinstance(message, list) and message and isinstance(message[0], dict):
            if "project_planner_output" in message[0]:
                message_str = message
                message_str_only = message[0].get("project_planner_output", "")
            else:
                raise ValueError("Invalid list format: expected dict with 'project_planner_output'")
        else:
            message_str = message
            message_str_only = message

        if existing_session:
            # Append to existing session
            await chat_collection.update_one(
                {"sessionId": session_id},
                {
                    "$push": {"msg": {"type": msg_type, "content": message_str}},
                    "$set": {"updated_at": datetime.utcnow()}
                }
            )
            logger.info("✅ Message appended to existing session.")
        else:
            # Create new session
            chat_doc = {
                "sessionId": session_id,
                "msg": [{"type": msg_type, "content": message_str}],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await chat_collection.insert_one(chat_doc)

            chat_doc_only = {
                "sessionId": session_id,
                "msg": [{"type": msg_type, "content": message_str_only}],
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            await mongodb.database["chat_only_history"].insert_one(chat_doc_only)

            logger.info("✅ New session created.")

        return True

    except Exception as e:
        logger.error(f"❌ Error in upsert_message_in_session: {e}")
        return False


async def fetch_message_history(session_id: str, last_n_messages: int = -5) -> str:
    chat_collection = mongodb.database[settings.users_chat_collection]
    document = await chat_collection.find_one(
        {"sessionId": session_id},
        {"msg": {"$slice": last_n_messages}}  # Slices the last n messages
    )
    
    # Check if document exists and has messages
    if not document or "msg" not in document or not document["msg"]:
        return "No messages found."

    # Handle normal case - return formatted message history
    msg_str = "\n".join(f"{msg['type']}: {msg['content']}" for msg in document["msg"])
    return msg_str

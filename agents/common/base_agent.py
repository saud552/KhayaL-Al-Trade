import asyncio
from faststream import FastStream
from faststream.redis import RedisBroker
from loguru import logger
from pydantic_settings import BaseSettings

class AgentSettings(BaseSettings):
    redis_url: str = "redis://localhost:6379"
    db_url: str = "postgresql://khaval_admin:khaval_password@localhost:5432/khaval_trade"
    ollama_url: str = "http://localhost:11434/v1"
    agent_name: str = "base_agent"

    class Config:
        env_file = ".env"

class BaseAgent:
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.broker = RedisBroker(settings.redis_url)
        self.app = FastStream(self.broker)
        self.name = settings.agent_name

    async def start(self):
        logger.info(f"Starting agent: {self.name}")
        await self.app.run()

    async def publish_signal(self, signal_data: dict):
        await self.broker.publish(
            signal_data,
            stream="agent:signals:stream",
        )
        logger.info(f"Signal published by {self.name}: {signal_data.get('signal')}")

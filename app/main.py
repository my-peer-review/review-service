# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings
from app.database.mongo_review import MongoReviewRepository
from app.routers.v1 import health
from app.routers.v1 import review

from app.database.mongo_events import MongoSubmissionDeliveredRepository
from app.services.consumer_service import ReviewSubmissionConsumer
from app.services.publisher_service import ReviewPublisher

import logging
import sys

logging.basicConfig(
    level=logging.INFO,  # cambia in DEBUG quando debuggiamo
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
    stream=sys.stdout,
)

# opzionale: più verboso solo per i nostri namespace
logging.getLogger("report.consumer").setLevel(logging.DEBUG)
logging.getLogger("report.repository").setLevel(logging.DEBUG)

def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        client = AsyncIOMotorClient(settings.mongo_uri, uuidRepresentation="standard")
        db = client[settings.mongo_db_name]
        repo = MongoReviewRepository(db)
        await repo.ensure_indexes()
        app.state.review_repo = repo

        # <<< NEW: repo + consumer submissions
        event_repo = MongoSubmissionDeliveredRepository(db)
        await event_repo.ensure_indexes()
        app.state.event_repo = event_repo

        # Config RabbitMQ da settings
        consumer = ReviewSubmissionConsumer(
            rabbitmq_url = settings.rabbitmq_url,
            repo = event_repo,
            exchange_name="elearning.submissions-consegnate",
            routing_key="submissions.reviews",
            queue_name="submissions.reviews",
            durable=True
        )
        app.state.review_consumer = consumer
        await consumer.start()

        # --- RabbitMQ Publisher ---
        publisher = ReviewPublisher(
            rabbitmq_url=settings.rabbitmq_url,
            heartbeat= 30,
            exchange = "elearning.reports",
            routing_key = "reviews.reports",
        )
        app.state.review_publisher = publisher
        await publisher.connect(max_retries=10, delay=5)

        try:
            yield
        finally:
            # Shutdown
            try:
                await consumer.stop()
                await publisher.close()
            finally:
                client.close()

    app = FastAPI(
        title="Assignment Microservice",
        description="Microservizio per la gestione degli assignment",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(CORSMiddleware,
        allow_origins=["*"], allow_credentials=True,
        allow_methods=["*"], allow_headers=["*"],
    )

    app.include_router(health.router, prefix="/api/v1", tags=["health"])
    app.include_router(review.router, prefix="/api/v1", tags=["review"])
    return app

app = create_app()
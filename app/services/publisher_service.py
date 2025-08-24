import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel, AbstractExchange, AbstractQueue

logger = logging.getLogger(__name__)

class ReviewPublisher:

    def __init__(
        self,
        rabbitmq_url: str,
        heartbeat: int,
        exchange: str = "elearning.reports",
        routing_key: str = "reviews.reports",
    ) -> None:
        self.rabbitmq_url = rabbitmq_url
        self.heartbeat = heartbeat
        self.exchange_name = exchange
        self.routing_key = routing_key

        self._conn: Optional[AbstractRobustConnection] = None
        self._channel: Optional[AbstractRobustChannel] = None
        self._exchange: Optional[AbstractExchange] = None
        self._temp_queue: Optional[AbstractQueue] = None
        self._lock = asyncio.Lock()

    async def connect(self, max_retries: int = 5, delay: int = 3) -> None:
        """Apre connessione e dichiara exchange/queue con retry/backoff."""
        attempt = 0
        while True:
            try:
                logger.debug("Tentativo connessione RabbitMQ #%s", attempt + 1)
                self._conn = await aio_pika.connect_robust(self.rabbitmq_url, heartbeat=self.heartbeat)
                self._channel = await self._conn.channel(publisher_confirms=True)
                await self._channel.set_qos(prefetch_count=10)

                self._exchange = await self._channel.declare_exchange(
                    self.exchange_name, ExchangeType.DIRECT, durable=True
                )

                logger.info("Connessione a RabbitMQ stabilita.")
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                logger.warning("Connessione fallita: %s", exc)
                if attempt >= max_retries:
                    logger.error("Impossibile connettersi a RabbitMQ dopo %s tentativi.", max_retries)
                    raise
                await asyncio.sleep(delay)

    async def close(self) -> None:
        """Chiude in modo pulito canale e connessione."""
        async with self._lock:
            try:
                if self._channel and not self._channel.is_closed:
                    logger.debug("Chiusura canale RabbitMQ.")
                    await self._channel.close()
            finally:
                if self._conn and not self._conn.is_closed:
                    logger.debug("Chiusura connessione RabbitMQ.")
                    await self._conn.close()
            self._conn = None
            self._channel = None
            self._exchange = None
            self._temp_queue = None

    async def _ensure_ready(self) -> None:
        if not self._conn or self._conn.is_closed:
            logger.debug("Connessione non attiva: provo a riconnettermi.")
            await self.connect()
        if not self._channel or self._channel.is_closed:
            logger.debug("Canale non attivo: riapro il canale.")
            assert self._conn is not None
            self._channel = await self._conn.channel(publisher_confirms=True)
        if not self._exchange:
            logger.debug("Exchange non presente in cache: lo dichiaro/recupero.")
            assert self._channel is not None
            self._exchange = await self._channel.declare_exchange(
                self.exchange_name, ExchangeType.DIRECT, durable=True
            )

    async def publish_review_report(
        self,
        submissionId: str,
        reviewId: str,
        punteggio: float,
        deliveredAt: datetime
    ) -> None:
        """
        Pubblica un messaggio di cambiamento stato assignment con payload JSON:
        { assignmentId, status, createdAt, completedAt }
        """
        await self._ensure_ready()
        assert self._exchange is not None

        payload = {
            "submissionId": submissionId,
            "reviewId": reviewId,
            "punteggio": punteggio,
            "deliveredAt" : deliveredAt.isoformat()
        }

        body = json.dumps(payload).encode("utf-8")
        msg = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.NOT_PERSISTENT,
            headers={"eventType": "assignment.status.changed"},
        )

        logger.debug(
            "Publishing su exchange=%s, routing_key=%s, payload=%s",
            self.exchange_name,
            self.routing_key,
            payload,
        )

        try:
            await self._exchange.publish(msg, routing_key=self.routing_key, mandatory=True)
            logger.debug(
                "Messaggio pubblicato con successo.",
            )
        except Exception as exc:
            logger.exception("Errore durante la pubblicazione del messaggio: %s", exc)
            raise

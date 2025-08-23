# app/review_consumer.py
import asyncio
import json
import logging
from typing import Any, Mapping, Optional

import aio_pika
from aio_pika import ExchangeType, IncomingMessage
from aiormq.exceptions import ChannelPreconditionFailed
from app.database.event_repo import SubmissionEventRepo

logger = logging.getLogger(__name__)

class ReviewSubmissionConsumer:
    """
    Consumer che dipende dall'interfaccia SubmissionEventRepo (DIP).
    Il repo viene passato dall'esterno (constructor injection).
    """
    def __init__(
        self,
        repo: SubmissionEventRepo,
        rabbitmq_url: str,
        heartbeat: int = 30,
        exchange_name: str = "elearning.submission-review",
        routing_key: str = "submission.review",
        queue_name: str = "elearning.submission-review.q.review",
        durable: bool = False,           # come richiesto
        prefetch_count: int = 20,
        requeue_on_error: bool = False,
    ) -> None:
        self.repo = repo
        self.rabbitmq_url = rabbitmq_url
        self.heartbeat = heartbeat
        self.review_exchange_name = exchange_name
        self.review_routing_key = routing_key
        self.queue_name = queue_name
        self.desired_durable = durable
        self.prefetch_count = prefetch_count
        self.requeue_on_error = requeue_on_error

        self._conn: Optional[aio_pika.RobustConnection] = None
        self._channel: Optional[aio_pika.RobustChannel] = None
        self._exchange: Optional[aio_pika.Exchange] = None
        self._queue: Optional[aio_pika.Queue] = None
        self._consumer_tag: Optional[str] = None

    async def start(self, max_retries: int = 10, delay: int = 5) -> None:
        attempt = 0
        while True:
            try:
                logger.info("Connessione a RabbitMQ… (%s/%s)", attempt + 1, max_retries)
                self._conn = await aio_pika.connect_robust(self.rabbitmq_url, heartbeat=self.heartbeat)
                self._channel = await self._conn.channel()
                await self._channel.set_qos(prefetch_count=self.prefetch_count)

                # Exchange: dichiara/ricrea in modo idempotente (se coerente)
                self._exchange = await self._channel.declare_exchange(
                    self.review_exchange_name,
                    ExchangeType.DIRECT,
                    durable=self.desired_durable,                    
                )

                # Queue del consumer
                self._queue = await self._channel.declare_queue(
                    name=self.queue_name,
                    durable=self.desired_durable,                  
                    exclusive=False,
                    auto_delete=False,
                )
                await self._queue.bind(self._exchange, routing_key=self.review_routing_key)
                logger.info("Queue pronta: %s -> %s rk=%s", self._queue.name, self.review_exchange_name, self.review_routing_key)

                # Start consume
                self._consumer_tag = await self._queue.consume(self._on_message, no_ack=False)
                logger.info("Consumo avviato (tag=%s, prefetch=%s)", self._consumer_tag, self.prefetch_count)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                attempt += 1
                logger.warning("Avvio consumer fallito: %s", exc, exc_info=True)
                if attempt >= max_retries:
                    logger.error("Impossibile avviare il consumer dopo %s tentativi.")
                    raise
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        try:
            if self._queue and self._consumer_tag:
                await self._queue.cancel(self._consumer_tag)
        except Exception:
            logger.exception("Errore cancel consumer")
        try:
            if self._channel and not self._channel.is_closed:
                await self._channel.close()
        except Exception:
            logger.exception("Errore chiusura canale")
        try:
            if self._conn and not self._conn.is_closed:
                await self._conn.close()
        except Exception:
            logger.exception("Errore chiusura connessione")
        self._conn = self._channel = self._exchange = self._queue = None
        self._consumer_tag = None

    def is_ready(self) -> bool:
        return bool(self._conn and not self._conn.is_closed and
                    self._channel and not self._channel.is_closed and
                    self._queue and self._exchange)

    async def _on_message(self, message: IncomingMessage) -> None:
        rk = message.routing_key
        mid = message.message_id
        logger.debug("Msg in arrivo rk=%s mid=%s", rk, mid)

        try:
            payload = json.loads(message.body.decode("utf-8"))
            logger.debug("Payload: %s", payload)

            created = await self.repo.save_message(payload)

            await message.ack()
            logger.info("Messaggio %s %s", mid or "(no-id)", "inserito" if created else "duplicato (ok)")

        except json.JSONDecodeError:
            logger.exception("JSON non valido: %r", message.body[:512])
            await message.nack(requeue=self.requeue_on_error)
        except Exception:
            logger.exception("Errore gestione messaggio")
            await message.nack(requeue=self.requeue_on_error)


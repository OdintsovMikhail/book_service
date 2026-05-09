import json
import os
import logging
from dotenv import load_dotenv
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

load_dotenv()

_SEND_CONN_STR   = os.getenv('AZURE_SERVICE_BUS_CONNECTION_STRING_SEND')
_LISTEN_CONN_STR = os.getenv('AZURE_SERVICE_BUS_CONNECTION_STRING_LISTEN')
QUEUE_NAME       = os.getenv('ASB_QUEUE_NAME')


class Source:
    BOOK    = "book"
    MEETING = "meeting"

SOURCE_BOOK    = Source.BOOK
SOURCE_MEETING = Source.MEETING


def _send_client() -> ServiceBusClient:
    if not _SEND_CONN_STR:
        raise RuntimeError("AZURE_SERVICE_BUS_CONNECTION_STRING_SEND is not set")
    return ServiceBusClient.from_connection_string(_SEND_CONN_STR)


def _listen_client() -> ServiceBusClient:
    if not _LISTEN_CONN_STR:
        raise RuntimeError("AZURE_SERVICE_BUS_CONNECTION_STRING_LISTEN is not set")
    return ServiceBusClient.from_connection_string(_LISTEN_CONN_STR)


async def publish(source: str, payload: dict) -> None:
    # Embed the source into the payload so the consumer can route it
    payload["source"] = source
    logging.info("sending message to %s queue", QUEUE_NAME)

    async with _send_client() as client:
        async with client.get_queue_sender(queue_name=QUEUE_NAME) as sender:
            msg = ServiceBusMessage(
                body=json.dumps(payload),
                content_type="application/json",
            )
            await sender.send_messages(msg)

            logging.info("mesage sent")
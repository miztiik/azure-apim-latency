import json
import logging
import datetime
import time
import os
import random
import uuid
import socket

import azure.functions as func
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.eventhub import EventHubProducerClient
from azure.eventhub import EventData
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import SpanKind
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

# ANSI color codes
GREEN_COLOR = "\033[32m"
RED_COLOR = "\033[31m"
RESET_COLOR = "\033[0m"

# Setup Tracing
tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": "store-backend-ops-consumer"}))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)
# This is the exporter that sends data to Application Insights
span_exporter = AzureMonitorTraceExporter(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING",
                                "InstrumentationKey=332f3080-ae91a73c0bad;IngestionEndpoint=https://northeurope-2.in.applicationinsights.azure.com/;LiveEndpoint=https://northeurope.livediagnostics.monitor.azure.com/")
)
span_processor = BatchSpanProcessor(span_exporter)
tracer_provider.add_span_processor(span_processor)

# Example usage with logging
logging.info(f'{GREEN_COLOR}This is green text{RESET_COLOR}')


class GlobalArgs:
    OWNER = "Mystique"
    VERSION = "2023-11-21"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    EVNT_WEIGHTS = {"success": 80, "fail": 20}
    TRIGGER_RANDOM_FAILURES = os.getenv("TRIGGER_RANDOM_FAILURES", True)
    WAIT_SECS_BETWEEN_MSGS = int(os.getenv("WAIT_SECS_BETWEEN_MSGS", 2))
    TOT_MSGS_TO_PRODUCE = int(os.getenv("TOT_MSGS_TO_PRODUCE", 10))

    APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=332f3080-ae91a73c0bad;IngestionEndpoint=https://northeurope-2.in.applicationinsights.azure.com/;LiveEndpoint=https://northeurope.livediagnostics.monitor.azure.com/")

    SVC_BUS_CONNECTION_STR = os.getenv("SVC_BUS_CONNECTION_STR")
    SVC_BUS_FQDN = os.getenv(
        "SVC_BUS_FQDN", "warehouse-q-svc-bus-ns-002.servicebus.windows.net")
    SVC_BUS_Q_NAME = os.getenv("SVC_BUS_Q_NAME", "warehouse-q-svc-bus-q-002")
    SVC_BUS_TOPIC_NAME = os.getenv(
        "SVC_BUS_TOPIC_NAME", "warehouse-ne-topic-002")

    EVENT_HUB_FQDN = os.getenv(
        "EVENT_HUB_FQDN", "warehouse-event-hub-ns-event-hub-streams-002.servicebus.windows.net")
    EVENT_HUB_NAME = os.getenv("EVENT_HUB_NAME", "store-events-stream-002")

    SA_NAME = os.getenv("SA_NAME", "warehousenehcqw3o002")
    BLOB_SVC_ACCOUNT_URL = os.getenv(
        "BLOB_SVC_ACCOUNT_URL", "https://warehousenehcqw3o002.blob.core.windows.net")
    BLOB_NAME = os.getenv("BLOB_NAME", "store-events-blob-002")
    BLOB_PREFIX = "store_events/raw"

    COSMOS_DB_URL = os.getenv(
        "COSMOS_DB_URL", "https://open-telemetry-ne-db-account-002.documents.azure.com:443/")
    COSMOS_DB_NAME = os.getenv(
        "COSMOS_DB_NAME", "open-telemetry-ne-db-account-002")
    COSMOS_DB_CONTAINER_NAME = os.getenv(
        "COSMOS_DB_CONTAINER_NAME", "store-backend-container-002")

    SVC_BUS_FQDN = os.getenv(
        "SVC_BUS_FQDN", "warehouse-q-svc-bus-ns-002.servicebus.windows.net")
    SVC_BUS_Q_NAME = os.getenv("SVC_BUS_Q_NAME", "warehouse-q-svc-bus-q-002")
    SVC_BUS_TOPIC_NAME = os.getenv(
        "SVC_BUS_TOPIC_NAME", "warehouse-q-svc-bus-q-002")

    EVENT_HUB_FQDN = os.getenv(
        "EVENT_HUB_FQDN", "warehouse-event-hub-ns-partition-processor-003.servicebus.windows.net")
    EVENT_HUB_NAME = os.getenv("EVENT_HUB_NAME", "store-events-stream-003")
    EVENT_HUB_SALE_EVENTS_CONSUMER_GROUP_NAME = os.getenv(
        "EVENT_HUB_SALE_EVENTS_CONSUMER_GROUP_NAME", "sale-events-consumers-003")


def _rand_coin_flip():
    r = False
    if GlobalArgs.TRIGGER_RANDOM_FAILURES:
        r = random.choices([True, False], weights=[0.1, 0.9], k=1)[0]
    return r


def _gen_uuid():
    return str(uuid.uuid4())


def write_to_blob(container_prefix, data: dict, blob_svc_client):
    # with tracer.start_span("mizt_upload_to_blob") as span:
    with tracer.start_as_current_span("mizt_upload_to_blob") as span:
        span.set_attribute("event_type", data["event_type"])
        span.set_attribute("is_return", data["is_return"])
        try:
            blob_name = f"{GlobalArgs.BLOB_PREFIX}/event_type={container_prefix}/dt={datetime.datetime.now().strftime('%Y_%m_%d')}/{datetime.datetime.now().strftime('%s%f')}.json"
            resp = blob_svc_client.get_blob_client(
                container=f"{GlobalArgs.BLOB_NAME}", blob=blob_name).upload_blob(json.dumps(data).encode("UTF-8"))
            logging.info(
                f"Blob {GREEN_COLOR}{blob_name}{RESET_COLOR} uploaded successfully")
        except Exception as e:
            logging.exception(f"ERROR:{str(e)}")


def write_to_cosmosdb(data: dict, db_container):
    # with tracer.start_span("mizt_upload_to_cosmos") as span:
    with tracer.start_as_current_span("mizt_upload_to_cosmos", kind=SpanKind.SERVER) as span:
        span.set_attribute("event_type", data["event_type"])
        span.set_attribute("is_return", data["is_return"])
        try:
            resp = db_container.create_item(body=data)
            logging.info(
                f"Document with id {GREEN_COLOR}{data['id']}{RESET_COLOR} written to CosmosDB successfully")
            logging.debug(f"{resp}")
        except Exception as e:
            logging.exception(f"ERROR:{str(e)}")
            span.record_exception(e)


def main(msg: func.ServiceBusMessage) -> str:
    _a_resp = {"status": False,
               "miztiik_event_processed": False}
    msg_body = msg.get_body().decode("utf-8")

    try:
        result = json.dumps({
            'message_id': msg.message_id,
            'body': msg.get_body().decode('utf-8'),
            'content_type': msg.content_type,
            'delivery_count': msg.delivery_count,
            'expiration_time': (msg.expiration_time.isoformat() if
                                msg.expiration_time else None),
            'label': msg.label,
            'partition_key': msg.partition_key,
            'reply_to': msg.reply_to,
            'reply_to_session_id': msg.reply_to_session_id,
            'scheduled_enqueue_time': (msg.scheduled_enqueue_time.isoformat() if
                                       msg.scheduled_enqueue_time else None),
            'delivery_count': msg.delivery_count,
            'session_id': msg.session_id,
            'time_to_live': msg.time_to_live,
            'to': msg.to,
            'user_properties': msg.user_properties,
            'event_type': msg.user_properties.get('event_type')
        })

        logging.info(f"{json.dumps(msg_body, indent=4)}")
        logging.info(f"recv_msg: {result}")

        azure_log_level = logging.getLogger("azure").setLevel(logging.ERROR)
        default_credential = DefaultAzureCredential(
            logging_enable=False, logging=azure_log_level)

        blob_svc_client = BlobServiceClient(
            GlobalArgs.BLOB_SVC_ACCOUNT_URL, credential=default_credential, logging=azure_log_level)

        cosmos_client = CosmosClient(
            url=GlobalArgs.COSMOS_DB_URL, credential=default_credential)
        db_client = cosmos_client.get_database_client(
            GlobalArgs.COSMOS_DB_NAME)
        db_container = db_client.get_container_client(
            GlobalArgs.COSMOS_DB_CONTAINER_NAME)

        # Trigger random failures
        if not json.loads(msg_body).get("store_id"):
            with tracer.start_span("event_without_store_id_received") as span:
                span.set_attribute("is_store_id_missing", "true")
                raise Exception("Store ID not found in the message")

        # write to blob
        _evnt_type = msg.user_properties.get("event_type")
        write_to_blob(_evnt_type, json.loads(msg_body), blob_svc_client)

        # write to cosmosdb
        write_to_cosmosdb(json.loads(msg_body), db_container)
        _a_resp["status"] = True
        _a_resp["miztiik_event_processed"] = True
        _a_resp["last_processed_on"] = datetime.datetime.now().isoformat()
        logging.info(f"{GREEN_COLOR} {json.dumps(_a_resp)} {RESET_COLOR}")

    except Exception as e:
        logging.exception(f"ERROR:{str(e)}")
        raise e

    logging.info(json.dumps(_a_resp, indent=4))

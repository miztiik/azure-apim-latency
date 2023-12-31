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
from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

# ANSI color codes
GREEN_COLOR = "\033[32m"
RED_COLOR = "\033[31m"
RESET_COLOR = "\033[0m"

# Setup Tracing
tracer_provider = TracerProvider(
    resource=Resource.create({"service.name": "producer"}))
trace.set_tracer_provider(tracer_provider)
tracer = trace.get_tracer(__name__)
# This is the exporter that sends data to Application Insights

span_exporter = AzureMonitorTraceExporter(
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING",
                                "InstrumentationKey=9ea96b76-8897-4639-9f6c-acdb1de39338;IngestionEndpoint=https://eastus-8.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus.livediagnostics.monitor.azure.com/")
)
span_processor = BatchSpanProcessor(span_exporter)
tracer_provider.add_span_processor(span_processor)

# Example usage with logging
logging.info(f'{GREEN_COLOR}This is green text{RESET_COLOR}')


class GlobalArgs:
    OWNER = "Mystique"
    VERSION = "2023-12-24"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    EVNT_WEIGHTS = {"success": 80, "fail": 20}
    TRIGGER_RANDOM_FAILURES = os.getenv("TRIGGER_RANDOM_FAILURES", True)
    WAIT_SECS_BETWEEN_MSGS = int(os.getenv("WAIT_SECS_BETWEEN_MSGS", 2))
    TOT_MSGS_TO_PRODUCE = int(os.getenv("TOT_MSGS_TO_PRODUCE", 1))

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
        "SVC_BUS_FQDN", "latency-us-store-events-svc-bus-ns-004.servicebus.windows.net")
    SVC_BUS_Q_NAME = os.getenv(
        "SVC_BUS_Q_NAME", "store-events-us-q-latency-004")
    SVC_BUS_TOPIC_NAME = os.getenv(
        "SVC_BUS_TOPIC_NAME", "store-events-us-topic-latency-004")

    EVENT_HUB_FQDN = os.getenv(
        "EVENT_HUB_FQDN", "latency-us-store-events-svc-bus-ns-004.servicebus.windows.net")
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


def generate_event():

    # Following Patterns are implemented
    # If event_type is inventory_event, then is_return is True for 50% of the events
    # 10% of total events are poison pill events, bad_msg attribute is True and store_id is removed
    # Event attributes are set with priority_shipping, is_return, and event type

    _categories = ["Books", "Games", "Mobiles", "Groceries", "Shoes", "Stationaries", "Laptops", "Tablets",
                   "Notebooks", "Camera", "Printers", "Monitors", "Speakers", "Projectors", "Cables", "Furniture"]
    _variants = ["black", "red"]
    _evnt_types = ["sale_event", "inventory_event"]
    _currencies = ["USD", "INR", "EUR", "GBP",
                   "AUD", "CAD", "SGD", "JPY", "CNY", "HKD"]
    _payments = ["credit_card", "debit_card", "cash",
                 "wallet", "upi", "net_banking", "cod", "gift_card"]

    _qty = random.randint(1, 99)
    _s = round(random.random() * 100, 2)

    _evnt_type = random.choices(_evnt_types, weights=[0.8, 0.2], k=1)[0]
    _u = _gen_uuid()
    p_s = random.choices([True, False], weights=[0.3, 0.7], k=1)[0]
    _promo = random.choices([True, False], weights=[0.13, 0.87], k=1)[0]
    is_return = False

    if _evnt_type == "inventory_event":
        is_return = bool(random.getrandbits(1))

    evnt_body = {
        "id": _u,
        "event_type": _evnt_type,
        "store_id": random.randint(1, 10),
        "store_fqdn": str(socket.getfqdn()),
        "store_ip": str(socket.gethostbyname(socket.gethostname())),
        "cust_id": random.randint(100, 999),
        "category": random.choice(_categories),
        "sku": random.randint(18981, 189281),
        "price": _s,
        "qty": _qty,
        "currency": random.choice(_currencies),
        "discount": random.randint(0, 75),
        "gift_wrap": random.choices([True, False], weights=[0.3, 0.7], k=1)[0],
        "variant": random.choice(_variants),
        "priority_shipping": p_s,
        "is_promoted": _promo,
        "payment_method": random.choice(_payments),
        "ts": datetime.datetime.now().isoformat(),
        "contact_me": "github.com/miztiik",
        "is_return": is_return
    }

    if _rand_coin_flip():
        evnt_body.pop("store_id", None)
        evnt_body["bad_msg"] = True

    _attr = {
        "event_type": _evnt_type,
        "priority_shipping": str(p_s),
        "is_return": str(is_return)
    }

    return evnt_body, _attr


def evnt_producer(event_cnt: int):
    resp = {
        "status": False,
        "tot_msgs": 0
    }

    try:
        t_msgs = 0
        p_cnt = 0
        s_evnts = 0
        inventory_evnts = 0
        t_sales = 0

        # Start timing the event generation
        event_gen_start_time = time.time()

        while t_msgs < event_cnt:
            with tracer.start_as_current_span(f"miztiik-event-{t_msgs}-trace") as span:
                evnt_body, evnt_attr = generate_event()
                span.set_attribute("event_id", evnt_body["id"])
            t_msgs += 1
            t_sales += evnt_body["price"] * evnt_body["qty"]

            if evnt_body.get("bad_msg"):
                p_cnt += 1

            if evnt_attr["event_type"] == "sale_event":
                s_evnts += 1
            elif evnt_attr["event_type"] == "inventory_event":
                inventory_evnts += 1

            time.sleep(GlobalArgs.WAIT_SECS_BETWEEN_MSGS)
            logging.info(f"generated_event:{json.dumps(evnt_body)}")

            # write to blob
            _evnt_type = evnt_attr["event_type"]
            # write_to_blob(_evnt_type, evnt_body, blob_svc_client)

            # # Ingest to CosmosDB
            # doc.set(func.Document.from_json(json.dumps(evnt_body)))
            # logging.info('Document injestion success')

            # Write To Service Bus Queue
            # write_to_svc_bus_q(evnt_body, evnt_attr)

            # # Write To Service Bus Topic
            write_to_svc_bus_topic(evnt_body, evnt_attr)

            # Write To Event Hub
            # write_to_event_hub(evnt_body, evnt_attr)

            # write to cosmosdb
            # write_to_cosmosdb(evnt_body, db_container)

        event_gen_end_time = time.time()  # Stop timing the event generation
        # Calculate the duration
        event_gen_duration = round(
            event_gen_end_time - event_gen_start_time, 3)

        resp["event_gen_duration"] = event_gen_duration
        resp["tot_msgs"] = t_msgs
        resp["bad_msgs"] = p_cnt
        resp["sale_evnts"] = s_evnts
        resp["inventory_evnts"] = inventory_evnts
        resp["tot_sales"] = t_sales
        resp["status"] = True
        # logging.info(f'{GREEN_COLOR} {{"resp":{json.dumps(resp)}}} {RESET_COLOR}')

    except Exception as e:
        logging.error(f"ERROR: {type(e).__name__}: {str(e)}")
        resp["err_msg"] = f"ERROR: {type(e).__name__}: {str(e)}"

    return resp


def write_to_svc_bus_topic(data, _attr):
    # Setup up Azure Credentials
    azure_log_level = logging.getLogger("azure").setLevel(logging.ERROR)
    credential = DefaultAzureCredential(
        logging_enable=False, logging=azure_log_level)

    with tracer.start_as_current_span("mizt_write_to_topic") as span:
        span.set_attribute("event_type", data["event_type"])
        span.set_attribute("is_return", data["is_return"])

        with ServiceBusClient(GlobalArgs.SVC_BUS_FQDN, credential=credential) as client:
            with client.get_topic_sender(topic_name=GlobalArgs.SVC_BUS_TOPIC_NAME) as sender:
                # Sending a single message
                msg_to_send = ServiceBusMessage(
                    json.dumps(data),
                    time_to_live=datetime.timedelta(days=1),
                    application_properties=_attr
                )

                _r = sender.send_messages(msg_to_send)
                logging.info(f"Event written to topic: {json.dumps(_r)}")
                logging.debug(f"Message sent: {json.dumps(_r)}")


def main(req: func.HttpRequest) -> func.HttpResponse:
    recv_cnt = 0
    req_body = {}
    _d = {
        "miztiik_event_processed": False,
        "msg": ""
    }

    # Setup Azure Clients
    # azure_log_level = logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)

    # Get Config data from App Config
    # _get_n_set_app_config(credential)

    try:
        try:
            recv_cnt = req.params.get("count")
            if recv_cnt:
                recv_cnt = recv_cnt
            logging.debug(f"got from params: {recv_cnt}")
        except ValueError:
            pass
        if not recv_cnt:
            try:
                req_body = req.get_json()
            except ValueError:
                _d["msg"] = "Message count not found in body"
                logging.debug("Message count not found in body")
                pass
            else:
                recv_cnt = req_body.get("count")

        logging.info(f"Received Count: {recv_cnt}")

        if recv_cnt:
            _d["event_count"] = int(recv_cnt)
        else:
            _d["event_count"] = GlobalArgs.TOT_MSGS_TO_PRODUCE

        print("inside main-to call evnt_producer")
        resp = evnt_producer(_d["event_count"])

        _d["resp"] = resp
        if resp.get("status"):
            _d["miztiik_event_processed"] = True
            # _d["headers"] = dict(req.headers)
            _d["msg"] = f"Generated {resp.get('tot_msgs')} messages"
            _d["last_processed_on"] = datetime.datetime.now().isoformat()
        logging.info(f"{GREEN_COLOR} {json.dumps(_d)} {RESET_COLOR}")
    except Exception as e:
        logging.exception(f"ERROR:{str(e)}")
        _d["msg"] = f"ERROR:{str(e)}"

    return func.HttpResponse(
        f"{json.dumps(_d, indent=4)}",
        status_code=200
    )


def local_run_only():
    main(func.HttpRequest(
        method='GET',
        body=b'',
        url='/api/evnt_producer',
        params={
            'count': '10'
        },
        headers=None,
        route_params=None,
    ))


if __name__ == "__main__":
    local_run_only()

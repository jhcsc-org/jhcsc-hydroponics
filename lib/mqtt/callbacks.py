# mqtt_module/callbacks.py

from awscrt import mqtt
import sys
import logging

logger = logging.getLogger(__name__)

def on_connection_interrupted(connection, error, **kwargs):
    """
    Callback when the MQTT connection is unexpectedly lost.
    """
    logger.warning(f"Connection interrupted. Error: {error}")

def on_connection_resumed(connection, return_code, session_present, **kwargs):
    """
    Callback when an interrupted MQTT connection is re-established.
    If the session did not persist, resubscribe to existing topics.
    """
    logger.info(f"Connection resumed. Return code: {return_code} Session present: {session_present}")

    if return_code == mqtt.ConnectReturnCode.ACCEPTED and not session_present:
        logger.info("Session did not persist. Resubscribing to existing topics...")
        resubscribe_future, _ = connection.resubscribe_existing_topics()

        # Cannot synchronously wait for resubscribe result because we're on the connection's event-loop thread,
        # evaluate result with a callback instead.
        resubscribe_future.add_done_callback(on_resubscribe_complete)

def on_resubscribe_complete(resubscribe_future):
    """
    Callback when resubscription to existing topics is complete.
    """
    resubscribe_results = resubscribe_future.result()
    logger.info(f"Resubscribe results: {resubscribe_results}")

    for topic, qos in resubscribe_results['topics']:
        if qos is None:
            logger.error(f"Server rejected resubscribe to topic: {topic}")
            sys.exit(f"Server rejected resubscribe to topic: {topic}")

def on_message_received(topic, payload, dup, qos, retain, **kwargs):
    """
    Callback when a message is received on a subscribed topic.
    """
    logger.info(f"Received message from topic '{topic}': {payload}")
    # Message handling logic will be managed in the PubSubClient

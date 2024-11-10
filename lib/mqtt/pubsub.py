# mqtt_module/pubsub.py

import sys
import threading
import time
import json
import logging

from awscrt import mqtt

from .connection import MQTTConnectionManager
from .callbacks import on_message_received

logger = logging.getLogger(__name__)

class PubSubClient:
    """
    Implements the MQTT Pub/Sub functionality.
    """

    def __init__(self, config):
        self.config = config
        self.received_count = 0
        self.received_all_event = threading.Event()
        self.connection_manager = MQTTConnectionManager(config)
        self.mqtt_connection = self.connection_manager.mqtt_connection

        # Assign the message received callback
        # Wrap the original callback to include counting
        self.mqtt_connection.on_message_received = self._on_message_received_wrapper

    def _on_message_received_wrapper(self, topic, payload, dup, qos, retain, **kwargs):
        """
        Wrapper for the message received callback to handle synchronization.
        """
        on_message_received(topic, payload, dup, qos, retain)
        self.received_count += 1
        if self.received_count == self.config.COUNT:
            self.received_all_event.set()

    def connect(self):
        """
        Connects to the MQTT broker.
        """
        try:
            self.connection_manager.connect()
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            raise

    def subscribe(self):
        """
        Subscribes to the specified MQTT topic.
        """
        message_topic = self.config.TOPIC
        logger.info(f"Subscribing to topic '{message_topic}'...")
        try:
            subscribe_future, packet_id = self.mqtt_connection.subscribe(
                topic=message_topic,
                qos=mqtt.QoS.AT_LEAST_ONCE,
                callback=self._on_message_received_wrapper
            )
            subscribe_result = subscribe_future.result()
            logger.info(f"Subscribed with QoS {subscribe_result['qos']}")
        except Exception as e:
            logger.error(f"Failed to subscribe: {e}")
            sys.exit(1)

    def publish(self, topic=None, message=None, publish_get=False):
        """
        Publishes a single message to the specified MQTT topic.
        
        Args:
            topic (str, optional): Custom topic to publish to. Defaults to config TOPIC.
            message (str, optional): Message to publish. Defaults to config MESSAGE.
            publish_get (bool, optional): If True, allows empty message for get requests. Defaults to False.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if not topic:
            logger.error("Cannot publish - topic is required")
            return False

        if not publish_get and message is None:
            logger.error("Cannot publish - message is required for non-get publications")
            return False

        logger.info(f"Publishing message to topic: '{topic}'")
        message_json = "{}" if publish_get else json.dumps(message)
        
        try:
            self.mqtt_connection.publish(
                topic=topic,
                payload=message_json,
                qos=mqtt.QoS.AT_LEAST_ONCE
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False
        

    def wait_for_messages(self):
        """
        Waits until all expected messages are received.
        """
        if self.config.COUNT != 0 and not self.received_all_event.is_set():
            logger.info("Waiting for all messages to be received...")
        self.received_all_event.wait()
        logger.info(f"{self.received_count} message(s) received.")

    def disconnect(self):
        """
        Disconnects from the MQTT broker.
        """
        self.connection_manager.disconnect()

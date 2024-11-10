import logging
import time
from .pubsub import PubSubClient
from awscrt import mqtt
from .callbacks import on_connection_interrupted, on_connection_resumed

logger = logging.getLogger(__name__)

class MultiTopicPubSubClient(PubSubClient):
    """
    Extends PubSubClient to support multiple topic subscriptions with different callbacks.
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.callbacks = {}  # Store callbacks for different topics
        self.subscribed_topics = set()  # Keep track of subscribed topics
        self.is_connected = False
        self._setup_connection_callbacks()

    def _setup_connection_callbacks(self):
        """Setup connection event callbacks."""
        self.mqtt_connection.on_connection_interrupted = self._on_connection_interrupted
        self.mqtt_connection.on_connection_resumed = self._on_connection_resumed

    def _on_connection_interrupted(self, connection, error, **kwargs):
        """Handle connection interruption."""
        self.is_connected = False
        logger.warning(f"Connection interrupted. Error: {error}")
        # Call the base callback
        on_connection_interrupted(connection, error, **kwargs)
        # Attempt to reconnect
        self._attempt_reconnect()

    def _on_connection_resumed(self, connection, return_code, session_present, **kwargs):
        """Handle connection resumption."""
        self.is_connected = True
        logger.info(f"Connection resumed. Return code: {return_code}")
        # Call the base callback
        on_connection_resumed(connection, return_code, session_present, **kwargs)
        
        if not session_present:
            logger.info("Session did not persist. Resubscribing to topics...")
            self._resubscribe_to_topics()

    def _attempt_reconnect(self, max_retries=5, delay=5):
        """Attempt to reconnect with exponential backoff."""
        retry_count = 0
        while not self.is_connected and retry_count < max_retries:
            try:
                logger.info(f"Attempting to reconnect... (Attempt {retry_count + 1}/{max_retries})")
                self.connect()
                
                # If connection successful, resubscribe to all topics
                if self.is_connected:
                    logger.info("Reconnection successful, resubscribing to topics...")
                    self._resubscribe_to_topics()
                    break
                    
            except Exception as e:
                retry_count += 1
                wait_time = delay * (2 ** retry_count)
                logger.error(f"Reconnection attempt failed: {e}. Waiting {wait_time} seconds...")
                time.sleep(wait_time)

        if not self.is_connected:
            logger.error("Failed to reconnect after maximum retries")

    def _resubscribe_to_topics(self):
        """Resubscribe to all previously subscribed topics."""
        for topic in self.subscribed_topics:
            try:
                self._subscribe_to_topic(topic)
                logger.info(f"Resubscribed to topic: {topic}")
            except Exception as e:
                logger.error(f"Failed to resubscribe to topic {topic}: {e}")

    def _subscribe_to_topic(self, topic):
        """Internal method to perform the actual subscription."""
        subscribe_future, packet_id = self.mqtt_connection.subscribe(
            topic=topic,
            qos=mqtt.QoS.AT_LEAST_ONCE,
            callback=self._handle_message
        )
        subscribe_result = subscribe_future.result()
        logger.info(f"Subscribed to {topic} with QoS {subscribe_result['qos']}")

    def subscribe(self, topic, callback=None, qos=1):
        """
        Subscribe to a specific topic with a custom callback.
        
        Args:
            topic (str): The topic to subscribe to
            callback (callable, optional): Callback function for this specific topic
            qos (int, optional): Quality of Service level. Defaults to 1
        """
        logger.info(f"Subscribing to topic '{topic}'...")
        try:
            if callback:
                self.callbacks[topic] = callback

            self._subscribe_to_topic(topic)
            self.subscribed_topics.add(topic)
            
        except Exception as e:
            logger.error(f"Failed to subscribe to {topic}: {e}")
            raise

    def _handle_message(self, topic, payload, dup, qos, retain, **kwargs):
        """
        Internal message handler that routes messages to topic-specific callbacks.
        """
        try:
            if topic in self.callbacks:
                self.callbacks[topic](topic, payload, dup=dup, qos=qos, retain=retain, **kwargs)
            else:
                logger.warning(f"Received message for topic {topic} but no callback registered")
        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    def disconnect(self):
        """
        Cleanly disconnect and clear subscriptions.
        """
        try:
            self.subscribed_topics.clear()
            self.callbacks.clear()
            self.is_connected = False
            super().disconnect()
        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
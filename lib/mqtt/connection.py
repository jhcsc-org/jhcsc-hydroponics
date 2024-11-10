# mqtt_module/connection.py

from awsiot import mqtt_connection_builder
from awscrt import mqtt, http
from .callbacks import (
    on_connection_interrupted,
    on_connection_resumed,
    on_resubscribe_complete,
    on_message_received
)
import logging

logger = logging.getLogger(__name__)

class MQTTConnectionManager:
    """
    Manages the MQTT connection, including building the connection and handling connection events.
    """

    def __init__(self, config):
        self.config = config
        self.mqtt_connection = self._build_connection()

    def _build_connection(self):
        """
        Builds the MQTT connection using mutual TLS authentication.
        """
        logger.info("Building MQTT connection...")
        return mqtt_connection_builder.mtls_from_path(
            endpoint=self.config.ENDPOINT,
            cert_filepath=self.config.PATH_TO_CERT,
            pri_key_filepath=self.config.PATH_TO_KEY,
            ca_filepath=self.config.PATH_TO_ROOT_CA,
            on_connection_interrupted=on_connection_interrupted,
            on_connection_resumed=on_connection_resumed,
            client_id=self.config.CLIENT_ID,
            clean_session=False,
            keep_alive_secs=30,
            on_connection_success=self.on_connection_success,
        )

    def connect(self):
        """
        Initiates the MQTT connection.
        """
        logger.info(f"Connecting to {self.config.ENDPOINT} with client ID '{self.config.CLIENT_ID}'...")
        connect_future = self.mqtt_connection.connect()
        connect_future.result()  # Wait for connection to complete
        logger.info("Connected!")

    def disconnect(self):
        """
        Gracefully disconnects the MQTT connection.
        """
        logger.info("Disconnecting...")
        disconnect_future = self.mqtt_connection.disconnect()
        disconnect_future.result()
        logger.info("Disconnected!")

    # Callback handlers specific to connection success and failure
    def on_connection_success(self, connection, callback_data):
        """
        Callback when the connection is successfully established.
        """
        logger.info(f"Connection Successful with return code: {callback_data.return_code} Session present: {callback_data.session_present}")

    def on_connection_failure(self, connection, callback_data):
        """
        Callback when the connection attempt fails.
        """
        logger.error(f"Connection failed with error code: {callback_data.error}")

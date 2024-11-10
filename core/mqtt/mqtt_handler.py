import logging
import math
import json
import time
from typing import Optional
from config.settings import (
    ENDPOINT, CLIENT_ID, 
    TOPIC_TEMPERATURE, TOPIC_HUMIDITY, TOPIC_LIGHT, TOPIC_PH,
    TOPIC_RELAY_STATUS,
    PATH_TO_CERT, PATH_TO_KEY, PATH_TO_ROOT_CA,
    UNIFIED_REALTIME_TOPIC, USE_UNIFIED_REALTIME_TOPIC
)
from lib.mqtt.mqtt_subscriber import MultiTopicPubSubClient
from services.relay_handler import RelayHandler
from utils.data_processor import DataProcessor
from services.command_handler import CommandHandler, RelayCommand

logger = logging.getLogger(__name__)

# ! NOTE TO SELF:
# ! Make sure all certificates are properly set up in AWS IoT Core
# ! Certificates should be in the specified paths from settings
class MQTTConfig:
    """
    Configuration for AWS IoT Core MQTT client.
    """
    ENDPOINT = ENDPOINT
    CLIENT_ID = CLIENT_ID
    PATH_TO_CERT = PATH_TO_CERT
    PATH_TO_KEY = PATH_TO_KEY
    PATH_TO_ROOT_CA = PATH_TO_ROOT_CA
    
    # Topic mapping for different sensor types
    # ? Consider moving this to a separate config file if it grows
    TOPICS = {
        "temperature": TOPIC_TEMPERATURE,
        "humidity": TOPIC_HUMIDITY,
        "light_level": TOPIC_LIGHT,
        "ph_levels": TOPIC_PH,
        "relay_states": TOPIC_RELAY_STATUS
    }

    # Shadow-specific topics for relays
    THING_NAME = "verdure"
    SHADOW_NAME = "relays"
    SHADOW_PREFIX = f"$aws/things/{THING_NAME}/shadow/name/{SHADOW_NAME}"
    
    # Complete set of shadow topics for robust operation
    SHADOW_TOPICS = {
        # Core operation topics
        "get": f"{SHADOW_PREFIX}/get",                    # Request current state
        "get/accepted": f"{SHADOW_PREFIX}/get/accepted",  # Receive current state
        "get/rejected": f"{SHADOW_PREFIX}/get/rejected",  # Get request failed
        "update": f"{SHADOW_PREFIX}/update",              # Report state changes
        "update/delta": f"{SHADOW_PREFIX}/update/delta",  # Receive desired state changes
        # Confirmation topics
        "update/accepted": f"{SHADOW_PREFIX}/update/accepted",  # Update confirmed
        "update/rejected": f"{SHADOW_PREFIX}/update/rejected",  # Update failed
    }

class MQTTHandler:
    """Handles MQTT communication with AWS IoT Core.
    
    Supports two modes:
    1. Unified topic: All sensor data published to one topic
    2. Split topics: Each sensor type published to its own topic
    
    * Use unified topic for simpler processing
    * Use split topics for more granular control
    """

    def __init__(self, relay_handler=None, command_handler=None):
        """Initialize MQTT handler with relay control."""
        self.relay_handler = relay_handler
        self.command_handler = command_handler
        self.client = MultiTopicPubSubClient(MQTTConfig)
        if self.client:
            self.client.connect()
            self._subscribe_to_shadow_topics()
            # Request initial state for synchronization
            self.request_shadow_state()

    def publish(self, sensor_data, compress=False):
        """Publish sensor data to AWS IoT Core.
        
        Args:
            sensor_data: Dictionary of sensor readings
            compress: Whether to compress data before sending
            
        * Note: Uses unified or split topics based on USE_UNIFIED_REALTIME_TOPIC setting
        ! Warning: Make sure topics are properly set up in AWS IoT Core
        """
        try:
            if not self.client:
                return

            if USE_UNIFIED_REALTIME_TOPIC:
                self._publish_unified(sensor_data, compress)
            else:
                self._publish_split(sensor_data, compress)

        except Exception as e:
            logger.error(f"Error publishing to AWS IoT Core: {e}")

    def _sanitize_sensor_value(self, key: str, value: any) -> any:
        """Sanitize sensor values to ensure consistent formatting.
        
        Args:
            key: Sensor type key
            value: Raw sensor value
            
        Returns:
            Sanitized value (-1 for invalid numeric readings)
        """
        if key in ['temperature', 'humidity', 'light_level']:
            if value in ['--', None] or (isinstance(value, float) and math.isnan(value)):
                return -1.0
            return round(float(value), 2)  # Round to 2 decimal places
            
        elif key == 'ph_levels':
            if not isinstance(value, list):
                return [-1.0] * 5  # Return array of -1s if invalid
            return [round(float(x), 2) if x != -1.0 else x for x in value]  # Round valid pH values
                
        elif key == 'relay_states':
            if not isinstance(value, list):
                return [False] * 5  # Return array of False if invalid
            return value
            
        return value
    
    def _publish_unified(self, sensor_data, compress):
        """Publish all sensor data to a single topic."""
        # Filter and sanitize sensor values
        sanitized_data = {
            k: self._sanitize_sensor_value(k, v)
            for k, v in sensor_data.items()
            if k in MQTTConfig.TOPICS
        }
        
        # Remove "relay_states" from sanitized data
        if "relay_states" in sanitized_data:
            del sanitized_data["relay_states"]
        
        # Create the new payload format
        payload = {
            "data_type": "sensor_data",
            "timestamp": int(time.time() * 1000),  # Current time in milliseconds
            **sanitized_data  # Unpack sanitized sensor data
        }

        if payload:
            success = self.client.publish(
                topic=UNIFIED_REALTIME_TOPIC,
                message=payload
            )
            if success:
                logger.debug(f"Published unified data to {UNIFIED_REALTIME_TOPIC}: {payload}")
            else:
                logger.error(f"Failed to publish unified data to {UNIFIED_REALTIME_TOPIC}")
    
    def _publish_split(self, sensor_data, compress):
        """Publish each sensor reading to its dedicated topic.
        
        Args:
            sensor_data: Dictionary of sensor readings
            compress: Whether to compress data
            
        * Used when USE_UNIFIED_REALTIME_TOPIC is False
        """
        # Publish each sensor type separately
        for data_type, topic in MQTTConfig.TOPICS.items():
            if data_type in sensor_data:
                value = sensor_data[data_type]
                if value not in ['--', [], None]:
                    # Prepare payload
                    payload = {data_type: value}
                    
                    # Add relay labels if publishing relay states
                    if data_type == 'relay_states':
                        payload['relay_labels'] = sensor_data.get('relay_labels', [])

                    # Optionally compress
                    encoded_data = DataProcessor.compress_data(payload) if compress else payload

                    success = self.client.publish(
                        topic=topic,
                        message=encoded_data
                    )

                    if success:
                        logger.debug(f"Published to {topic}: {payload}")
                    else:
                        logger.error(f"Failed to publish to topic: {topic}")

    def _subscribe_to_shadow_topics(self):
        """Subscribe to all relevant shadow topics."""
        topics = [
            # Core operation topics
            MQTTConfig.SHADOW_TOPICS["get/accepted"],     # For initial sync
            MQTTConfig.SHADOW_TOPICS["get/rejected"],     # Handle sync failures
            MQTTConfig.SHADOW_TOPICS["update/delta"],     # For external changes
            # Confirmation topics
            MQTTConfig.SHADOW_TOPICS["update/accepted"],  # Update confirmations
            MQTTConfig.SHADOW_TOPICS["update/rejected"],  # Update failures
        ]
        
        for topic in topics:
            self.client.subscribe(topic, callback=self._on_message_received)
            logger.debug(f"Subscribed to topic: {topic}")

    def report_all_relay_states(self):
        """Report current states of all relays to the shadow."""
        if not self.relay_handler:
            return

        reported_state = {
            "state": {
                "reported": {}
            }
        }

        # Get all relay states
        states = self.relay_handler.get_relay_states()
        
        # Build the reported state (only states, not labels)
        for i, state in enumerate(states):
            relay_key = f"relay{i + 1}"
            reported_state["state"]["reported"][relay_key] = {
                "state": state
            }

        success = self.client.publish(
            topic=MQTTConfig.SHADOW_TOPICS["update"],
            message=reported_state
        )
        
        if success:
            logger.debug(f"Reported all relay states: {reported_state}")
        else:
            logger.error("Failed to report relay states to shadow")

    def report_relay_state(self, index: int, state: bool):
        """Report current state of a specific relay to the shadow.
        
        Args:
            index: Relay index (0-based)
            state: Current state of the relay
        """
        relay_key = f"relay{index + 1}"
        payload = {
            "state": {
                "reported": {
                    relay_key: {
                        "state": state
                    }
                }
            }
        }
        
        success = self.client.publish(
            topic=MQTTConfig.SHADOW_TOPICS["update"],
            message=payload
        )
        
        if success:
            logger.debug(f"Reported relay state: {payload}")
        else:
            logger.error(f"Failed to report relay state for {relay_key}")

    def _handle_shadow_delta(self, payload):
        """Handle changes in desired state from shadow."""
        try:
            delta = payload.get('state', {})
            for relay_key, relay_data in delta.items():
                if not relay_key.startswith('relay') or not isinstance(relay_data, dict):
                    continue

                relay_index = self._extract_relay_index(relay_key)
                if relay_index is None:
                    continue

                new_state = relay_data.get('state')
                if new_state is None:
                    continue

                self._process_relay_state_change(relay_index, new_state)
                time.sleep(0.1)  # Add a short delay between commands
        except Exception as e:
            logger.error(f"Error handling shadow delta: {e}")

    def _extract_relay_index(self, relay_key):
        """Extract relay index from relay key."""
        try:
            return int(relay_key[5:]) - 1
        except ValueError:
            logger.error(f"Invalid relay key format: {relay_key}")
            return None

    def _process_relay_state_change(self, relay_index, new_state):
        """Process relay state change."""
        current_state = self.relay_handler.get_relay_state(relay_index)
        if current_state == new_state:
            logger.debug(f"Relay {relay_index} already in desired state: {new_state}")
            return

        logger.info(f"Enqueuing command to update relay {relay_index} to state: {new_state}")
        command = RelayCommand(relay_index=relay_index, state=new_state)
        self.command_handler.handle_relay_toggle(command)

        # Wait for relay to update state
        time.sleep(0.5)  # Wait for relay to change state

        # Verify the state change before reporting
        actual_state = self.relay_handler.get_relay_state(relay_index)
        if actual_state == new_state:
            self.report_relay_state(relay_index, new_state)
            logger.debug(f"Relay {relay_index} state change verified and reported")
        else:
            logger.warning(f"Relay {relay_index} state change could not be verified")

    def request_shadow_state(self):
        """Request current shadow state with error handling."""
        success = self.client.publish(
            topic=MQTTConfig.SHADOW_TOPICS["get"],
            message={},
            publish_get=True
        )
        
        if success:
            logger.info("Requested current shadow state for synchronization")
        else:
            logger.error("Failed to request shadow state")

    def _on_message_received(self, topic, payload, **kwargs):
        """Handle incoming MQTT messages."""
        try:
            payload_str = payload.decode('utf-8')
            payload_json = json.loads(payload_str)
            logger.debug(f"Received message on topic {topic}: {payload_json}")
            
            if topic == MQTTConfig.SHADOW_TOPICS["update/delta"]:
                # Handle desired state changes
                self._handle_shadow_delta(payload_json)
                
            elif topic == MQTTConfig.SHADOW_TOPICS["get/accepted"]:
                # Handle initial state sync
                if "state" in payload_json and "desired" in payload_json["state"]:
                    self._handle_shadow_delta({"state": payload_json["state"]["desired"]})
                    # After handling desired state, avoid reporting all states to prevent conflicts
                    # self.report_all_relay_states()
                    
            elif topic == MQTTConfig.SHADOW_TOPICS["get/rejected"]:
                logger.error(f"Shadow get request rejected: {payload_json}")
                
            elif topic == MQTTConfig.SHADOW_TOPICS["update/accepted"]:
                logger.debug("Shadow update confirmed")
                
            elif topic == MQTTConfig.SHADOW_TOPICS["update/rejected"]:
                error_msg = payload_json.get("message", "Unknown error")
                logger.error(f"Shadow update rejected: {error_msg}")
                
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON payload: {e}")
        except Exception as e:
            logger.error(f"Error processing message on topic {topic}: {e}")
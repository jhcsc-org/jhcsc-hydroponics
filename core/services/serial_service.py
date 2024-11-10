import logging
import time
import json
from config.settings import MQTT_PUBLISH_INTERVAL, SerialConfig
from lib.proto_serial.serial_exceptions import SerialConnectionError
from core import socketio

logger = logging.getLogger(__name__)

class SerialService:
    """Manages serial communication and real-time data distribution.
    
    Handles:
    - Serial data reading and parsing
    - Real-time updates via SocketIO
    - MQTT publishing for cloud sync
    - Relay state management
    
    This is the main service that bridges hardware and web interface
    """

    def __init__(self, serial_handler, sensor_parser, relay_handler, relay_config, mqtt_handler):
        """Initialize serial service with required handlers.
        
        Args:
            serial_handler: Manages raw serial communication
            sensor_parser: Parses raw data into structured format
            relay_handler: Manages relay states
            relay_config: Stores relay configuration
            mqtt_handler: Handles cloud communication
        """
        # core components
        self.serial_handler = serial_handler
        self.sensor_parser = sensor_parser
        self.relay_handler = relay_handler
        self.relay_config = relay_config
        self.mqtt_handler = mqtt_handler
        
        # maintain last known sensor values
        # * used for UI updates and error handling
        self.last_sensor_data = {
            'temperature': '--',  # -- indicates no reading
            'humidity': '--',
            'light_level': '--',
            'ph_levels': []
        }
        
        # mqtt throttling
        self.last_publish_time = time.time()  # tracks last mqtt publish

    def read_serial_data(self):
        """Continuously reads and processes serial data.
        
        Main loop that:
        1. Reads raw serial data
        2. Parses sensor readings
        3. Updates UI via SocketIO
        4. Syncs to cloud via MQTT
        
        ? consider adding watchdog timer for hardware monitoring
        """
        while True:
            try:
                # attempt to read data from serial
                data = self.serial_handler.read_message()
                if not data:
                    # no data available, wait before retry
                    # ! adjust READ_INTERVAL based on sensor update frequency
                    time.sleep(SerialConfig.READ_INTERVAL)
                    continue
                
                # parse raw data into structured format
                sensor_data = self.sensor_parser.parse(data)
                if sensor_data:
                    self._process_sensor_data(sensor_data)
                
            except SerialConnectionError as e:
                # handle connection issues gracefully
                logger.error(f"Serial connection error: {e}")
                time.sleep(SerialConfig.READ_INTERVAL)
            except Exception as e:
                # catch any other unexpected errors
                logger.error(f"Error in read_serial_data: {e}")
                time.sleep(SerialConfig.READ_INTERVAL)

    def _process_sensor_data(self, sensor_data):
        """Process and distribute sensor readings.
        
        Args:
            sensor_data: Parsed sensor readings
            
        * Note: This is where all real-time updates originate
        """
        # combine sensor data with relay states
        sensor_data_dict = sensor_data.to_dict()
        sensor_data_dict['relay_states'] = self.relay_handler.get_relay_states()
        sensor_data_dict['relay_labels'] = self.relay_config.labels
        
        # update cached values and notify clients
        self._update_last_sensor_data(sensor_data_dict)
        socketio.emit('sensor_data', sensor_data_dict)
        
        # handle cloud sync with rate limiting
        self._handle_mqtt_publish(sensor_data_dict)
        
        # log valid readings for debugging
        self._log_valid_data(sensor_data_dict)

    def _update_last_sensor_data(self, sensor_data_dict):
        """Update cached sensor values.
        
        Args:
            sensor_data_dict: New sensor readings
        """
        # keep track of last known good values
        self.last_sensor_data.update({
            'temperature': sensor_data_dict.get('temperature', '--'),
            'humidity': sensor_data_dict.get('humidity', '--'),
            'light_level': sensor_data_dict.get('light_level', '--'),
            'ph_levels': sensor_data_dict.get('ph_levels', [])
        })

    def _handle_mqtt_publish(self, sensor_data_dict):
        """Publish to MQTT with rate limiting.
        
        Args:
            sensor_data_dict: Data to publish
        """
        # NOTE: Respects MQTT_PUBLISH_INTERVAL to avoid flooding
        current_time = time.time()
        if current_time - self.last_publish_time >= MQTT_PUBLISH_INTERVAL:
            self.mqtt_handler.publish(sensor_data_dict)
            self.last_publish_time = current_time

    def _log_valid_data(self, sensor_data_dict):
        """Log non-empty sensor readings for debugging.
        
        Args:
            sensor_data_dict: Sensor data to log
        """
        # filter out empty/invalid readings
        valid_data = {k: v for k, v in sensor_data_dict.items() 
                     if v not in ['--', [], None]}
        if valid_data:
            logger.debug(f"Emitted sensor data: {json.dumps(valid_data, indent=2)}")
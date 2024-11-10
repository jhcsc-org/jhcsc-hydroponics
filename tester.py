#!/usr/bin/env python3
import serial
import time
import json
import logging
import argparse
import sys
from typing import Optional
from proto import hydroponics_pb2
from services.serial_handler import SerialHandler
from services.sensor_data_parser import SensorDataParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SerialTester:
    """Tester for reading serial data from hydroponics hardware using the project's services."""
    
    def __init__(self, port: str, baudrate: int = 115200, timeout: int = 1):
        """Initialize serial connection with services.
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0' or 'COM3')
            baudrate: Baud rate for serial communication
            timeout: Read timeout in seconds
        """
        # Initialize the serial handler with protobuf message type
        self.serial_handler = SerialHandler(proto_class=hydroponics_pb2.SensorData)
        self.serial_handler.serial_manager.port = port
        self.serial_handler.serial_manager.baud_rate = baudrate
        self.serial_handler.serial_manager.timeout = timeout
        
        # Initialize the sensor data parser
        self.sensor_parser = SensorDataParser()

    def connect(self) -> bool:
        """Establish serial connection using SerialHandler.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.serial_handler.connect()
            logger.info(f"Connected to {self.serial_handler.serial_manager.port} "
                       f"at {self.serial_handler.serial_manager.baud_rate} baud")
            return True
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        try:
            self.serial_handler.close()
            logger.info("Serial connection closed")
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    def read_and_parse_data(self) -> Optional[dict]:
        """Read and parse data using project services.
        
        Returns:
            dict: Parsed sensor data or None if read/parse failed
        """
        try:
            # Read raw message using SerialHandler
            raw_data = self.serial_handler.read_message()
            logger.debug(f"Raw data: {raw_data}")

            if not raw_data:
                return None

            # Try to parse as protobuf first
            sensor_data = self.sensor_parser.parse(raw_data)
            if sensor_data:
                logger.debug(f"Parsed sensor data: {sensor_data}")
                return sensor_data.to_dict()

            # If protobuf parsing fails, try JSON
            try:
                logger.debug(f"Raw data (decoded): {raw_data.decode('utf-8')}")
                return json.loads(raw_data.decode('utf-8'))
            except json.JSONDecodeError:
                logger.debug(f"Raw data (not JSON): {raw_data}")
                return None

        except Exception as e:
            logger.error(f"Error reading/parsing data: {e}")
            return None

    def monitor(self, duration: Optional[int] = None):
        """Monitor serial data for specified duration.
        
        Args:
            duration: How long to monitor in seconds (None for indefinite)
        """
        if not self.connect():
            return

        try:
            start_time = time.time()
            while True:
                # Check duration
                if duration and (time.time() - start_time) > duration:
                    logger.info(f"Monitoring completed after {duration} seconds")
                    break

                # Read and process data
                data = self.read_and_parse_data()
                if data:
                    # Pretty print the data
                    logger.info("Received sensor data:")
                    logger.info(json.dumps(data, indent=2))
                    
                    # Log specific sensor values
                    if 'temperature' in data:
                        logger.info(f"Temperature: {data['temperature']}°C")
                    if 'humidity' in data:
                        logger.info(f"Humidity: {data['humidity']}%")
                    if 'light_level' in data:
                        logger.info(f"Light Level: {data['light_level']}%")
                    if 'ph_levels' in data:
                        logger.info(f"pH Levels: {data['ph_levels']}")
                    if 'relay_states' in data:
                        logger.info(f"Relay States: {data['relay_states']}")
                
                time.sleep(0.1)  # Small delay to prevent CPU hogging

        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
        finally:
            self.disconnect()

def main():
    """Main entry point with command line argument parsing."""
    parser = argparse.ArgumentParser(description='Serial Port Tester for Hydroponics')
    
    parser.add_argument(
        '-p', '--port',
        required=True,
        help='Serial port (e.g., /dev/ttyUSB0 or COM3)'
    )
    
    parser.add_argument(
        '-b', '--baudrate',
        type=int,
        default=9600,
        help='Baud rate (default: 9600)'
    )
    
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=1,
        help='Read timeout in seconds (default: 1)'
    )
    
    parser.add_argument(
        '-d', '--duration',
        type=int,
        help='Monitoring duration in seconds (default: indefinite)'
    )

    args = parser.parse_args()

    # Create and run tester
    tester = SerialTester(
        port=args.port,
        baudrate=args.baudrate,
        timeout=args.timeout
    )
    
    tester.monitor(duration=args.duration)

if __name__ == "__main__":
    main()
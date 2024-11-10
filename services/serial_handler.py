import logging
from typing import Optional, Type
from lib.proto_serial.serial_connection import (
    SerialConnectionManager, ProtoMessage, 
    SerialConnectionError, SerialWriteError
)
from dataclasses import dataclass
from config.settings import (
    DEFAULT_SERIAL_PORT, DEFAULT_BAUD_RATE, 
    DEFAULT_TIMEOUT, DEFAULT_READ_SIZE
)
import struct
import time
import threading

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) 

@dataclass
class SensorReading:
    """Data structure for parsed sensor readings."""
    temperature: float
    humidity: float
    light_level: float
    ph_levels: list[float]
    relay_states: list[bool]

class SerialHandler:
    """Handles serial communication with Arduino using a message-based protocol.
    
    Uses a length-prefixed message format for reliable data transfer:
    [2 bytes length][message payload]
    
    ! Note: Make sure Arduino uses the same message format and byte order
    """

    def __init__(self, proto_class: Type[ProtoMessage]):
        """Initialize serial handler with protobuf message type.
        
        Args:
            proto_class: Protobuf message class for decoding incoming data
        """
        # store protobuf class for message decoding
        self.proto_class = proto_class
        
        # initialize serial connection manager with default settings
        # ? might want to make these configurable via environment vars
        self.serial_manager = SerialConnectionManager(
            proto_class=proto_class,
            port=DEFAULT_SERIAL_PORT,
            baud_rate=DEFAULT_BAUD_RATE,
            timeout=DEFAULT_TIMEOUT
        )
        self.lock = threading.Lock()

    def connect(self) -> None:
        """Establish serial connection and clear any stale data.
        
        Raises:
            Exception: If connection fails
        """
        try:
            self.serial_manager._connect()
            self.serial_manager.flush()  # clear any garbage data in buffer
        except Exception as e:
            # let caller handle connection failures
            logger.error(f"Failed to connect to serial port: {e}")
            raise

    def read_message(self) -> Optional[bytes]:
        """Read a length-prefixed message from serial port.
        
        Returns:
            bytes: Message payload if successful, None otherwise
        """
        with self.lock:
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    # Look for message start marker
                    while True:
                        byte = self.serial_manager.serial_connection.read(1)
                        if not byte:
                            time.sleep(0.1)
                            break
                        if byte == b'\xFF':  # Add start marker in Arduino code
                            next_byte = self.serial_manager.serial_connection.read(1)
                            if next_byte == b'\xFE':  # Complete start sequence
                                break
                
                    # Read length after finding marker
                    length_bytes = self.serial_manager.serial_connection.read(DEFAULT_READ_SIZE)
                    if len(length_bytes) != DEFAULT_READ_SIZE:
                        retry_count += 1
                        continue

                    message_length = struct.unpack('<H', length_bytes)[0]
                    
                    # Stricter length validation
                    MAX_MESSAGE_SIZE = 512  # Adjust based on your needs
                    if message_length == 0 or message_length > MAX_MESSAGE_SIZE:
                        logger.warning(f"Invalid message length: {message_length}")
                        retry_count += 1
                        continue

                    # Read message and verify end marker
                    message_data = self.serial_manager.serial_connection.read(message_length)
                    end_marker = self.serial_manager.serial_connection.read(2)
                    
                    if end_marker != b'\xFD\xFC':  # Add end marker in Arduino code
                        logger.warning("Invalid end marker")
                        retry_count += 1
                        continue

                    return message_data

                except SerialConnectionError as e:
                    logger.warning(f"Serial connection error: {e}")
                    retry_count += 1
                    continue
                    
                except Exception as e:
                    logger.error(f"Unexpected error reading message: {e}")
                    return None
                    
            return None  # Return None if all retries failed

    def write_command(self, command_data: bytes) -> None:
        """Write a length-prefixed command to serial port.
        
        Args:
            command_data: Raw command bytes to send
            
        Raises:
            SerialWriteError: If write fails
        """
        with self.lock:
            try:
                self.serial_manager.flush()  # Flush before writing
                message_length = len(command_data)
                length_bytes = struct.pack('<H', message_length)  # little endian
                full_message = length_bytes + command_data
                
                # send it all at once to avoid partial writes
                self.serial_manager.transmit_serial_data(full_message)
                self.serial_manager.flush()  # Flush after writing
                
            except SerialWriteError as e:
                # specific handling for write failures
                logger.error(f"Failed to write command: {e}")
                raise
            except Exception as e:
                # catch any other unexpected errors
                logger.error(f"Unexpected error writing command: {e}")
                raise

    def close(self) -> None:
        """Close serial connection cleanly."""
        try:
            self.serial_manager.close()
        except Exception as e:
            # log but don't raise - we're closing anyway
            logger.error(f"Error closing serial connection: {e}")
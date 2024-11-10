import serial
import serial.tools.list_ports
from typing import Any, Optional, List, Dict, TypeVar, Generic, Type
from datetime import datetime
from google.protobuf.message import Message
import time
import logging

from config.settings import DEFAULT_SERIAL_PORT, DEFAULT_BAUD_RATE, DEFAULT_TIMEOUT, DEFAULT_READ_SIZE
from lib.proto_serial.serial_exceptions import (
    SerialConnectionError,
    SerialPortNotFoundError,
    SerialWriteError,
    SerialTimeoutError,
    SerialBufferError,
)

ProtoMessage = TypeVar('ProtoMessage', bound=Message)

class SerialConnectionManager(Generic[ProtoMessage]):
    def __init__(
        self,
        proto_class: Type[ProtoMessage],
        port: str = DEFAULT_SERIAL_PORT,
        baud_rate: int = DEFAULT_BAUD_RATE,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """
        Initialize serial connection with specified parameters.
        
        Args:
            port: Serial port identifier
            baud_rate: Communication speed
            timeout: Read/write timeout in seconds
        """
        self.proto_class = proto_class
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.serial_connection: Optional[serial.Serial] = None
        self.connection_time: Optional[datetime] = None
        self._connect()

    def _connect(self) -> None:
        """Establish the serial connection with validation."""
        self._validate_serial_port()
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout
            )
            self.connection_time = datetime.now()
        except Exception as e:
            raise SerialConnectionError(
                message=f"Failed to initialize serial connection: {e}",
                port=self.port
            )

    def __enter__(self) -> 'SerialConnectionManager':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit with cleanup."""
        self.close()

    # First we need to retrieve the data from the serial connection
    def retrieve_serial_data(self) -> bytes:
        """
        Read a complete message from the serial connection.
        
        Returns:
            bytes: Raw data read from serial port
        
        Raises:
            SerialConnectionError: If connection is not open or read fails
        """
        if not self.is_open():
            self.reconnect()
            if not self.is_open():
                raise SerialConnectionError(
                    message="Serial connection is not open",
                    port=self.port
                )
            
        try:
            # Read with timeout
            if not self.serial_connection.in_waiting:
                return None
            
            # Read the message type (1 byte)
            msg_type = self.serial_connection.read(1)
            if not msg_type:
                return None
            
            # Read the message length (4 bytes)
            message_length_bytes = self.serial_connection.read(4)
            if not message_length_bytes:
                raise SerialTimeoutError(
                    port=self.port,
                    timeout=self.timeout,
                    operation="read"
                )
            message_length = int.from_bytes(message_length_bytes, byteorder='little')
            
            # Read the actual message
            encoded_data = self.serial_connection.read(message_length)
            if not encoded_data:
                raise SerialTimeoutError(
                    port=self.port,
                    timeout=self.timeout,
                    operation="read"
                )
            return encoded_data
        except serial.SerialException as e:
            raise SerialConnectionError(
                message=f"Serial read error: {str(e)}",
                port=self.port
            )

    # Then we need to decode the data to the protocol message
    def decode_serial_data(self, encoded_data: bytes):
        """
        Decode bytes data to a protocol message.
        
        Returns:
            Message: Decoded protocol message
        """
        message = self.proto_class()
        message.ParseFromString(encoded_data)
        return message
    
    # Finally we need to get the decoded data
    # TODO: Figure out how to get the hints for the proto message
    def get_decoded_data(self):
        """
        Get data from serial connection and decode to protocol message.
        
        Returns:
            ProtoMessage: Decoded protocol message
        """
        encoded_data = self.retrieve_serial_data()
        return self.decode_serial_data(encoded_data)

    def transmit_serial_data(self, data: bytes) -> None:
        """
        Write bytes data to serial connection.
        
        Args:
            data: Bytes to write to serial port
        """
        if not self.is_open():
            raise SerialConnectionError(
                message="Serial connection is not open",
                port=self.port
            )
        try:
            bytes_written = self.serial_connection.write(data)
            if bytes_written != len(data):
                raise SerialWriteError(
                    port=self.port,
                    data_length=len(data),
                    bytes_written=bytes_written
                )
        except Exception:
            raise SerialWriteError(
                port=self.port,
                data_length=len(data),
                bytes_written=0
            )

    def close(self) -> None:
        """Close the serial connection safely."""
        if self.serial_connection and self.is_open():
            try:
                self.serial_connection.close()
            except Exception as e:
                raise SerialConnectionError(
                    message=f"Error closing serial connection: {e}",
                    port=self.port
                )

    def is_open(self) -> bool:
        """Check if serial connection is open."""
        return bool(self.serial_connection and self.serial_connection.is_open)

    def flush(self) -> None:
        """Flush serial connection buffers."""
        if not self.is_open():
            raise SerialConnectionError(
                message="Serial connection is not open",
                port=self.port
            )
        try:
            self.serial_connection.flush()
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
        except Exception:
            raise SerialBufferError(
                port=self.port,
                operation="flush"
            )

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get current connection information.
        
        Returns:
            Dict containing connection details
        """
        return {
            "port": self.port,
            "baud_rate": self.baud_rate,
            "timeout": self.timeout,
            "is_open": self.is_open(),
            "connection_time": self.connection_time,
            "uptime": (datetime.now() - self.connection_time) if self.connection_time else None
        }

    @staticmethod
    def list_available_ports() -> List[str]:
        """
        List all available serial ports in the system.
        
        Returns:
            List of available port names
        """
        return [port.device for port in serial.tools.list_ports.comports()]

    def _validate_serial_port(self) -> None:
        """Validate if specified serial port exists."""
        available_ports = self.list_available_ports()
        if self.port not in available_ports:
            raise SerialPortNotFoundError(
                port=self.port,
                available_ports=available_ports
            )

    def reconnect(self) -> bool:
        """
        Attempt to reconnect to the serial port.
        
        Returns:
            bool: True if reconnection successful, False otherwise
        """
        try:
            if self.serial_connection:
                self.close()
            time.sleep(1)  # Wait before reconnecting
            self._connect()
            return True
        except Exception as e:
            logging.error(f"Failed to reconnect: {e}")
            return False

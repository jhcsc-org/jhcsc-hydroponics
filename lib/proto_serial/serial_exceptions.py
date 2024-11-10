class SerialConnectionError(Exception):
    """Base exception for serial connection errors."""
    def __init__(self, message: str = "Serial connection error occurred", port: str = None):
        self.port = port
        self.message = f"{message} {'on port ' + port if port else ''}"
        super().__init__(self.message)

class SerialPortNotFoundError(SerialConnectionError):
    """Raised when the specified serial port is not found."""
    def __init__(self, port: str, available_ports: list[str] = None):
        message = f"Serial port '{port}' not found"
        if available_ports:
            message += f". Available ports: {', '.join(available_ports)}"
        super().__init__(message, port)

class SerialDecodingError(SerialConnectionError):
    """Raised when data cannot be decoded properly."""
    def __init__(self, port: str = None, encoding: str = None, raw_data: bytes = None):
        message = "Failed to decode serial data"
        if encoding:
            message += f" using {encoding} encoding"
        if raw_data:
            message += f". Raw data: {raw_data!r}"
        super().__init__(message, port)

class SerialWriteError(SerialConnectionError):
    """Raised when data cannot be written to the port."""
    def __init__(self, port: str = None, data_length: int = None, bytes_written: int = None):
        message = "Failed to write data to serial port"
        if data_length is not None and bytes_written is not None:
            message += f". Only {bytes_written}/{data_length} bytes written"
        super().__init__(message, port)

class SerialTimeoutError(SerialConnectionError):
    """Raised when a serial operation times out."""
    def __init__(self, port: str = None, timeout: float = None, operation: str = None):
        message = "Serial operation timed out"
        if operation:
            message += f" during {operation}"
        if timeout:
            message += f" after {timeout} seconds"
        super().__init__(message, port)

class SerialConfigError(SerialConnectionError):
    """Raised when there's an invalid serial configuration."""
    def __init__(self, port: str = None, parameter: str = None, value: any = None):
        message = "Invalid serial configuration"
        if parameter and value:
            message += f": {parameter}={value}"
        super().__init__(message, port)

class SerialBufferError(SerialConnectionError):
    """Raised when there's a buffer overflow or underflow."""
    def __init__(self, port: str = None, buffer_size: int = None, operation: str = None):
        message = "Serial buffer error"
        if operation:
            message += f" during {operation}"
        if buffer_size:
            message += f". Buffer size: {buffer_size} bytes"
        super().__init__(message, port)
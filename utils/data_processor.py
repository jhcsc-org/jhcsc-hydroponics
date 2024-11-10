import json
import zlib
import base64
import logging

logger = logging.getLogger(__name__)

class DataProcessor:
    """Handles data compression and encoding for MQTT messages."""
    
    @staticmethod
    def compress_data(data: dict) -> str:
        """
        Compresses and encodes data for MQTT transmission.
        
        Args:
            data (dict): The data to compress and encode
            
        Returns:
            str: Base64 encoded compressed data
            
        Raises:
            Exception: If compression or encoding fails
        """
        try:
            # convert to json string
            json_str = json.dumps(data)
            # compress with maximum compression
            compressed = zlib.compress(json_str.encode('utf-8'), level=9)
            # encode to base64
            encoded = base64.b64encode(compressed).decode('utf-8')
            return encoded
        except Exception as e:
            logger.error(f"Failed to compress data: {e}")
            raise
    
    @staticmethod
    def decompress_data(encoded_data: str) -> dict:
        """
        Decodes and decompresses MQTT message data.
        
        Args:
            encoded_data (str): Base64 encoded compressed data
            
        Returns:
            dict: The decompressed data
            
        Raises:
            Exception: If decompression or decoding fails
        """
        try:
            # decode base64
            decoded = base64.b64decode(encoded_data)
            # decompress
            decompressed = zlib.decompress(decoded)
            # parse json
            data = json.loads(decompressed.decode('utf-8'))
            return data
        except Exception as e:
            logger.error(f"Failed to decompress data: {e}")
            raise 
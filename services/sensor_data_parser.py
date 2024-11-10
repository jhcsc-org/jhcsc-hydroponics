from typing import Optional
from dataclasses import dataclass
from proto import hydroponics_pb2
import logging

logger = logging.getLogger(__name__)

# ! currently not in active use - implemented for future optimization
# * will be essential when we need to minimize AWS IoT Core data transfer
# ? consider enabling when approaching AWS IoT Core quotas or for bandwidth optimization

@dataclass
class SensorData:
    """Data model for parsed sensor readings.
    
    Currently unused but implemented for future data optimization needs.
    Particularly useful when AWS IoT Core data transfer costs become a concern.
    """
    temperature: float
    humidity: float
    light_level: float
    ph_levels: list[float]
    relay_states: list[bool]

    def to_dict(self) -> dict:
        """Converts sensor data to a dictionary format.
        
        Returns:
            Dictionary with sensor readings, ready for JSON serialization
        """
        # keeping the structure flat for simpler processing
        return {
            'temperature': self.temperature,
            'humidity': self.humidity,
            'light_level': self.light_level,
            'ph_levels': self.ph_levels,
            'relay_states': self.relay_states
        }

class SensorDataParser:
    """Parses protobuf sensor data into structured format.
    
    - Currently bypassed in favor of direct JSON handling
    - Will be essential when we need to optimize data transfer
    
    Benefits of using this parser:
    - Reduces data size through protobuf compression
    - Provides structured data validation
    - Helps catch malformed data early
    """

    @staticmethod
    def parse(data: bytes) -> Optional[SensorData]:
        """Parse raw protobuf bytes into structured sensor data.
        
        Args:
            data: Raw protobuf-encoded sensor data
            
        Returns:
            Parsed SensorData object or None if parsing fails
            
        * Note: Currently unused as we're sending raw JSON
        * Enable this when data transfer optimization becomes necessary
        """
        def safe_value(value, default=-1):
            """Returns the value if it's not -1, otherwise returns the default."""
            return value if value != -1 else default
        
        def process_light_level(raw_light_value: float, offset: float = 0) -> float:
            """Processes the raw light level value from the sensor.
            
            Args:
                raw_light_value: The raw light level value from the sensor.
                offset: The offset to adjust the light level value.
            
            Returns:
                A processed light level value, scaled to a percentage.
            """
            # raw_light_value is on a scale from 0 to 1023
            # invert the scale: 0 becomes 100% and 1023 becomes 0%
            return raw_light_value + offset

        sensor_proto = hydroponics_pb2.SensorData()
        try:
            # decode protobuf message
            sensor_proto.ParseFromString(data)
            
            # convert to our internal format
            sensor_data = SensorData(
                temperature=safe_value(sensor_proto.temperature),
                humidity=safe_value(sensor_proto.humidity),
                light_level=process_light_level(sensor_proto.light_level),
                ph_levels=list(sensor_proto.ph_levels) if sensor_proto.ph_levels else [-1],
                relay_states=list(sensor_proto.relay_states) if sensor_proto.relay_states else []
            )
            return sensor_data
            
        except Exception as e:
            # log but don't crash - let caller handle missing data
            logger.error(f"Failed to parse sensor data: {e}")
            return None
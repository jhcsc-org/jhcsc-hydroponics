import os
import logging
import json
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=os.getenv("VERBOSITY", "INFO").upper())
logger = logging.getLogger(__name__)

# Load environment variables from .env
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
    logger.info(f"Loaded .env file from {env_path}")
else:
    logger.warning(f"No .env file found at {env_path}")

# AWS IoT Core configuration settings
THINGNAME: str = os.getenv("THINGNAME", "default_thing")
ENDPOINT: str = os.getenv("ENDPOINT", "your-default-endpoint.amazonaws.com")
CLIENT_ID: str = os.getenv("CLIENT_ID", "DefaultClientID")
CLIENT_ID_SUB: str = os.getenv("CLIENT_ID_SUB", "DefaultClientID_sub")

# Topics
TOPIC_TEMPERATURE: str = os.getenv("TOPIC_TEMPERATURE", "default/topic/temperature")
TOPIC_HUMIDITY: str = os.getenv("TOPIC_HUMIDITY", "default/topic/humidity")
TOPIC_LIGHT: str = os.getenv("TOPIC_LIGHT", "default/topic/light")
TOPIC_PH: str = os.getenv("TOPIC_PH", "default/topic/ph")
TOPIC_RELAY_CONTROL: str = os.getenv("TOPIC_RELAY_CONTROL", "default/topic/relay/control")
TOPIC_RELAY_STATUS: str = os.getenv("TOPIC_RELAY_STATUS", "default/topic/relay/status")

# Unified topic configuration
UNIFIED_REALTIME_TOPIC: str = os.getenv("UNIFIED_REALTIME_TOPIC", "default/topic/unified")
USE_UNIFIED_REALTIME_TOPIC: bool = os.getenv("USE_UNIFIED_REALTIME_TOPIC", "true").lower() == "true"

# Certifications
PATH_TO_CERT: str = os.getenv("PATH_TO_CERT", f"config/certs/{THINGNAME}.cert.pem")
PATH_TO_KEY: str = os.getenv("PATH_TO_KEY", f"config/certs/{THINGNAME}.private.key")
PATH_TO_ROOT_CA: str = os.getenv("PATH_TO_ROOT_CA", "config/certs/root-CA.crt")

# MQTT Message settings
MESSAGE: str = os.getenv("MESSAGE", "Hello MQTT!")

# Serial settings
DEFAULT_SERIAL_PORT: str = os.getenv("DEFAULT_SERIAL_PORT", "/dev/ttyUSB0")
DEFAULT_BAUD_RATE: int = int(os.getenv("DEFAULT_BAUD_RATE", 9600))
DEFAULT_TIMEOUT: float = float(os.getenv("DEFAULT_TIMEOUT", 1000))
DEFAULT_READ_SIZE: int = int(os.getenv("DEFAULT_READ_SIZE", 2))

# Interval settings
MQTT_PUBLISH_INTERVAL: float = float(os.getenv("MQTT_PUBLISH_INTERVAL", 5))  # seconds
SERIAL_READ_INTERVAL: float = float(os.getenv("SERIAL_READ_INTERVAL", 1))  # seconds

# Add to your existing FlaskConfig or create a new config section
class SerialConfig:
    PORT: str = DEFAULT_SERIAL_PORT
    BAUD_RATE: int = DEFAULT_BAUD_RATE
    TIMEOUT: int = DEFAULT_TIMEOUT
    READ_INTERVAL: int = SERIAL_READ_INTERVAL  # seconds between each read

@dataclass
class FlaskConfig:
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", 'secret!')
    HOST: str = os.getenv("FLASK_HOST", '0.0.0.0')
    PORT: int = int(os.getenv("FLASK_PORT", 5000))

@dataclass
class RelayConfig:
    labels: list = field(default_factory=lambda: ["Relay 0", "Relay 1", "Relay 2", "Relay 3", "Relay 4"])
    CONFIG_FILE: str = os.getenv('RELAY_CONFIG_FILE', 'config/relay_labels.json')

    def load_labels(self):
        # Get the absolute path relative to the project root
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.CONFIG_FILE)
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    self.labels = json.load(f)
                    logger.info("Loaded relay labels from file.")
            except json.JSONDecodeError:
                logger.error("JSON decode error. Using default relay labels.")
                self.save_labels()
        else:
            self.save_labels()

    def save_labels(self):
        try:
            # Get the absolute path relative to the project root
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), self.CONFIG_FILE)
            # Ensure the directory exists
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(self.labels, f, indent=4)
                logger.info("Saved relay labels to file.")
        except Exception as e:
            logger.error(f"Failed to save relay labels: {e}")

# Initialize RelayConfig
relay_config = RelayConfig()
relay_config.load_labels()
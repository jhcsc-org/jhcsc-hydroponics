import logging
import threading
import argparse
from config.settings import FlaskConfig, relay_config
from services.serial_handler import SerialHandler
from services.command_handler import CommandHandler
from services.sensor_data_parser import SensorDataParser
from services.relay_handler import RelayHandler
from lib.proto_serial.serial_exceptions import SerialConnectionError
from proto import hydroponics_pb2
from core import app, socketio
from core.mqtt.mqtt_handler import MQTTHandler
from core.services.serial_service import SerialService
from core.routes.api_routes import init_api_routes
from core.routes.socket_routes import init_socket_routes

logger = logging.getLogger(__name__)

def initialize_services():
    """
    Initialize essential services for the application.
    
    This function sets up the serial handler, relay handler, sensor parser, MQTT handler, and command handler. It returns these handlers for further use.
    
    Returns:
        tuple: Contains serial_handler, serial_service, and command_handler.
    """
    try:
        # setting up the serial handler to read data from the sensor
        serial_handler = SerialHandler(proto_class=hydroponics_pb2.SensorData)
        
        # configuring the relay handler to control the relays
        relay_handler = RelayHandler(number_of_relays=len(relay_config.labels))
        
        # initializing the sensor data parser
        sensor_parser = SensorDataParser()
        
        # command handler to process client commands
        command_handler = CommandHandler(
            serial_writer=serial_handler,
            relay_handler=relay_handler,
            socketio=socketio,
            get_relay_config=lambda: relay_config,
            get_last_sensor_data=lambda: serial_service.last_sensor_data
        )
        
        # setting up the mqtt handler for communication with AWS IoT Core
        # Pass both handlers to MQTT
        mqtt_handler = MQTTHandler(
            relay_handler=relay_handler,
            command_handler=command_handler  
        )
        
        # creating the serial service to manage serial data
        serial_service = SerialService(
            serial_handler=serial_handler,
            sensor_parser=sensor_parser,
            relay_handler=relay_handler,
            relay_config=relay_config,
            mqtt_handler=mqtt_handler
        )
        
        return serial_handler, serial_service, command_handler
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise

def start_serial_thread(serial_handler, serial_service):
    """
    Start a thread to read serial data from the sensor.
    
    This function initiates a background thread to continuously read data from the sensor and send it to the client.
    """
    try:
        # connect to the serial port
        serial_handler.connect()
        
        # start a daemon thread for reading serial data
        thread = threading.Thread(
            target=serial_service.read_serial_data,
            name="SerialReader"
        )
        thread.daemon = True
        thread.start()
        logger.info("Started serial data reading thread.")
    except SerialConnectionError as e:
        logger.error(f"Failed to start serial thread due to connection error: {e}")
        raise
    except Exception as e:
        logger.error(f"Failed to start serial thread: {e}")
        raise

def run_server(debug: bool = False): 
    """
    Run the server with optional debugging.
    
    This function sets the logging level, initializes services, sets up API 
    and socket routes, starts the serial thread, and runs the server.
    
    Args:
        debug (bool): If True, enables debugging mode.
    """
    try:
        # set logging level based on debug flag
        logger.setLevel(logging.DEBUG if debug else logging.DEBUG)
        
        # initialize the essential services
        serial_handler, serial_service, command_handler = initialize_services()
        
        # set up api routes for client interaction
        init_api_routes(
            command_handler,
            relay_config,
            serial_service.relay_handler,
            serial_service.last_sensor_data
        )
        
        # configure socket routes for real-time data transmission
        init_socket_routes(command_handler)
        
        # start the thread for reading serial data
        start_serial_thread(serial_handler, serial_service)
        
        # run the server using socketio
        socketio.run(app, host=FlaskConfig.HOST, port=FlaskConfig.PORT, debug=debug)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == '__main__':
    # parse command-line arguments for debugging
    parser = argparse.ArgumentParser(description="Run the server with optional debugging.")
    parser.add_argument('--debug', action='store_true', help="Enable debugging mode")
    args = parser.parse_args()
    
    # start the server with the specified debug setting
    run_server(debug=args.debug)
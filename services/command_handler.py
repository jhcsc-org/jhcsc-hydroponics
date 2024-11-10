from dataclasses import dataclass
from typing import Protocol, Callable
from proto import hydroponics_pb2
import logging
import threading
import queue
import time

logger = logging.getLogger(__name__)

# handles command processing and execution with a queue-based approach
# uses a worker thread to avoid blocking the main thread during serial operations

class SerialWriter(Protocol):
    """Protocol for writing commands to the serial connection."""
    
    def write_command(self, command_data: bytes) -> None:
        """Writes command data to the serial connection.
        
        Args:
            command_data: Raw bytes to be written to serial port.
        """
        # TODO: I have to implement this because the serial connection is handled by the serial service. currently it is mocked.

@dataclass
class RelayCommand:
    """Command data structure for relay operations."""
    relay_index: int
    state: bool = None  # if None, toggles current state. if bool, sets to specific state

    def execute(self, relay_handler):
        # direct execution without going through command queue
        if self.state is not None:
            relay_handler.set_relay_state(self.relay_index, self.state)
        else:
            relay_handler.toggle_relay(self.relay_index)

@dataclass
class CalibrationCommand:
    """Command data structure for pH sensor calibration."""
    sensor_index: int
    calibration_value: float

class CommandHandler:
    """Manages command creation, queueing, and execution with serial communication.
    
    Handles both relay control and pH sensor calibration commands through a 
    thread-safe queue system. Commands are processed sequentially to avoid 
    race conditions with the hardware.
    """

    def __init__(
        self, 
        serial_writer: SerialWriter, 
        relay_handler, 
        socketio, 
        get_relay_config: Callable, 
        get_last_sensor_data: Callable
    ):
        """Initialize command handling system.
        
        Args:
            serial_writer: Interface for serial communication
            relay_handler: Manages relay states
            socketio: For real-time updates
            get_relay_config: Callback to fetch relay settings
            get_last_sensor_data: Callback to get latest sensor readings
        """
        # core components for command processing
        self.serial_writer = serial_writer
        self.relay_handler = relay_handler
        self.socketio = socketio
        
        # callbacks for state management
        self.get_relay_config = get_relay_config
        self.get_last_sensor_data = get_last_sensor_data
        
        # queue system for thread-safe command processing
        self.command_queue = queue.Queue()
        
        # start worker thread for processing commands
        self.worker_thread = threading.Thread(
            target=self._process_commands, 
            name="CommandHandlerWorker",
            daemon=True  # allows clean shutdown
        )
        self.worker_thread.start()

    def _create_command(self, command_type: str, **kwargs) -> bytes:
        """Creates a protobuf-serialized command.
        
        Args:
            command_type: Type of command to create
            **kwargs: Command-specific parameters
        
        Returns:
            Serialized command bytes
        """
        # ! note: protobuf structure must match arduino expectations
        cmd = hydroponics_pb2.Command()
        
        if command_type == 'TOGGLE_RELAY':
            cmd.type = hydroponics_pb2.Command.TOGGLE_RELAY
            cmd.relay_index = kwargs.get('relay_index', 0)
            # ? consider adding explicit state control in protobuf
            
        elif command_type == 'CALIBRATE_PH':
            cmd.type = hydroponics_pb2.Command.CALIBRATE_PH
            cmd.ph_sensor_index = kwargs.get('sensor_index', 0)
            cmd.ph_calibration_value = kwargs.get('calibration_value', 7.0)
            
        else:
            # unknown command type - fail fast
            raise ValueError(f"Unknown command type: {command_type}")
        
        return cmd.SerializeToString()

    def send_command(self, command_type: str, **kwargs) -> None:
        """
        Creates and enqueues a command.

        Args:
            command_type (str): The type of command to send.
            **kwargs: Additional parameters for the command.
        """
        try:
            self.command_queue.put((command_type, kwargs))
            logger.info(f"Enqueued command of type: {command_type} with args: {kwargs}")
        except Exception as e:
            logger.error(f"Failed to enqueue command: {e}")

    def _process_commands(self):
        """Processes commands from the queue sequentially."""
        logger.info("Worker thread started processing commands.")
        while True:
            try:
                command_type, kwargs = self.command_queue.get()
                logger.info(f"Processing command: {command_type} with args: {kwargs}")
                
                if command_type == 'TOGGLE_RELAY':
                    relay_index = kwargs.get('relay_index')
                    state = kwargs.get('state')
                    
                    # Update local relay state first
                    if state is not None:
                        self.relay_handler.set_relay_state(relay_index, state)
                    else:
                        self.relay_handler.toggle_relay(relay_index)
                    
                    # Send command to hardware without state
                    serialized_command = self._create_command('TOGGLE_RELAY', relay_index=relay_index)
                    self.serial_writer.write_command(serialized_command)
                    logger.info(f"Toggle relay command sent for relay {relay_index}.")
                
                elif command_type == 'CALIBRATE_PH':
                    sensor_index = kwargs.get('sensor_index')
                    calibration_value = kwargs.get('calibration_value')
                    command = CalibrationCommand(sensor_index=sensor_index, calibration_value=calibration_value)
                    serialized_command = self._create_command('CALIBRATE_PH', sensor_index=sensor_index, calibration_value=calibration_value)
                    self.serial_writer.write_command(serialized_command)
                    logger.info(f"Calibration command sent for sensor {sensor_index} with value {calibration_value}.")

                # After command execution, emit updated relay states
                relay_config = self.get_relay_config()
                last_sensor_data = self.get_last_sensor_data()

                sensor_data_dict = {
                    'relay_states': self.relay_handler.get_relay_states(),
                    'relay_labels': relay_config.labels,
                    'temperature': last_sensor_data.get('temperature', '--'),
                    'humidity': last_sensor_data.get('humidity', '--'),
                    'light_level': last_sensor_data.get('light_level', '--'),
                    'ph_levels': last_sensor_data.get('ph_levels', [])
                }
                self.socketio.emit('sensor_data', sensor_data_dict)
                logger.info(f"Emitted updated sensor data after processing {command_type}.")

                self.command_queue.task_done()
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                self.command_queue.task_done()

    def handle_relay_toggle(self, command: RelayCommand) -> None:
        """
        Handles the relay toggle command by enqueuing it.

        Args:
            command (RelayCommand): Relay toggle command data.
        """
        logger.debug(f"Handling relay toggle: {command}")
        self.send_command('TOGGLE_RELAY', relay_index=command.relay_index, state=command.state)

    def handle_ph_calibration(self, command: CalibrationCommand, enqueue=True) -> None:
        """
        Handles the pH calibration command by enqueuing it.

        Args:
            command (CalibrationCommand): pH calibration command data.
            enqueue (bool): Whether to enqueue the command. Set to False when processing in the queue.
        """
        if enqueue:
            logger.debug(f"Enqueuing pH calibration: {command}")
            self.send_command(
                'CALIBRATE_PH', 
                sensor_index=command.sensor_index, 
                calibration_value=command.calibration_value
            )
        else:
            # Execute directly without enqueueing
            try:
                serialized_command = self._create_command(
                    'CALIBRATE_PH', 
                    sensor_index=command.sensor_index, 
                    calibration_value=command.calibration_value
                )
                self.serial_writer.write_command(serialized_command)
                logger.info(f"Executed calibration command for sensor {command.sensor_index}.")
            except Exception as e:
                logger.error(f"Failed to execute calibration command: {e}")
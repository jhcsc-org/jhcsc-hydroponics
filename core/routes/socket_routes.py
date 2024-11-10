import logging
from core import socketio
from services import relay_handler
from services.command_handler import CalibrationCommand, RelayCommand

logger = logging.getLogger(__name__)

def init_socket_routes(command_handler):
    @socketio.on('toggle_all_relays')
    def handle_toggle_all_relays(data):
        action = data.get('action')
        try:
            state = True if action == 'on' else False
            relay_count = len(command_handler.relay_handler.relay_states)
            
            for i in range(relay_count):
                command = RelayCommand(relay_index=i, state=state)
                command_handler.handle_relay_toggle(command)
                
            logger.info(f"Set all relays to {action.upper()} via SocketIO.")
        except Exception as e:
            logger.error(f"Failed to set all relays to {action.upper()} via SocketIO: {e}")

    @socketio.on('toggle_relay')
    def handle_toggle_relay(data: dict) -> None:
        relay_index = data.get('relay_index', 0)
        state = data.get('state', None)
        command = RelayCommand(relay_index=relay_index, state=state) if state is not None else RelayCommand(relay_index=relay_index)
        try:
            command_handler.handle_relay_toggle(command)
            logger.info(f"Toggled relay {relay_index} via SocketIO.")
        except Exception as e:
            logger.error(f"Failed to toggle relay via SocketIO: {e}")

    @socketio.on('calibrate_ph')
    def handle_calibrate_ph(data: dict) -> None:
        sensor_index = data.get('ph_sensor_index', 0)
        calibration_value = data.get('ph_calibration_value', 7.0)
        command = CalibrationCommand(
            sensor_index=sensor_index,
            calibration_value=calibration_value
        )
        try:
            command_handler.handle_ph_calibration(command)
            logger.info(f"Calibrated pH sensor {sensor_index} via SocketIO.")
        except Exception as e:
            logger.error(f"Failed to calibrate pH sensor via SocketIO: {e}") 
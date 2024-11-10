from flask import jsonify, request, render_template
import logging
from core import app, socketio
from services.command_handler import RelayCommand, CalibrationCommand

logger = logging.getLogger(__name__)

def init_api_routes(command_handler, relay_config, relay_handler, last_sensor_data):
    @app.route('/')
    def index():
        """Renders the main page."""
        return render_template('index.html')

    @app.route('/api/toggle_relay', methods=['POST'])
    def api_toggle_relay():
        data = request.get_json()
        relay_index = data.get('relay_index', 0)
        command = RelayCommand(relay_index=relay_index)
        try:
            command_handler.handle_relay_toggle(command)
            logger.info(f"Toggled relay {relay_index} via API.")
            return jsonify({"status": "success", "relay_index": relay_index}), 200
        except Exception as e:
            logger.error(f"Failed to toggle relay via API: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/calibrate_ph', methods=['POST'])
    def api_calibrate_ph():
        data = request.get_json()
        sensor_index = data.get('ph_sensor_index', 0)
        calibration_value = data.get('ph_calibration_value', 7.0)
        command = CalibrationCommand(
            sensor_index=sensor_index,
            calibration_value=calibration_value
        )
        try:
            command_handler.handle_ph_calibration(command)
            logger.info(f"Calibrated pH sensor {sensor_index} via API.")
            return jsonify({
                "status": "success", 
                "sensor_index": sensor_index, 
                "calibration_value": calibration_value
            }), 200
        except Exception as e:
            logger.error(f"Failed to calibrate pH sensor via API: {e}")
            return jsonify({"status": "error", "message": str(e)}), 500

    @app.route('/api/relay_labels', methods=['GET', 'POST'])
    def relay_labels():
        if request.method == 'GET':
            return jsonify({"labels": relay_config.labels}), 200
        elif request.method == 'POST':
            return _handle_relay_labels_update(
                request, relay_config, relay_handler, last_sensor_data
            )

def _handle_relay_labels_update(request, relay_config, relay_handler, last_sensor_data):
    data = request.get_json()
    new_labels = data.get('labels', [])
    if len(new_labels) != len(relay_config.labels):
        return jsonify({
            "status": "error", 
            "message": "Incorrect number of labels."
        }), 400
    
    relay_config.labels = new_labels
    relay_config.save_labels()

    sensor_data_dict = {
        'relay_states': relay_handler.get_relay_states(),
        'relay_labels': relay_config.labels,
        'temperature': last_sensor_data.get('temperature', '--'),
        'humidity': last_sensor_data.get('humidity', '--'),
        'light_level': last_sensor_data.get('light_level', '--'),
        'ph_levels': last_sensor_data.get('ph_levels', [])
    }
    socketio.emit('sensor_data', sensor_data_dict)
    logger.info(f"Emitted updated relay labels to clients after label change.")

    return jsonify({"status": "success", "labels": relay_config.labels}), 200 
#include "hydroponics.h"
#include "hydroponics.pb.h"
#include "pb.h"
#include "pb_encode.h"
#include "pb_decode.h"

// constructor - initialize everything
HydroponicsController::HydroponicsController()
    : dht(DHT_PIN, DHT11),
      lastSampleTime(0),
      lightLevel(0.0)
{
    // initialize pin arrays
    uint8_t ph_pins[] = PH_PINS;
    uint8_t relay_pins[] = RELAY_PINS;
    memcpy(phPins, ph_pins, sizeof(phPins));
    memcpy(relayPins, relay_pins, sizeof(relayPins));

    // init arrays to default values
    memset(relayStates, 0, sizeof(relayStates));
    memset(phLevels, 0, sizeof(phLevels));
    memset(relayStateBuffer, 0, sizeof(relayStateBuffer));
    memset(phCalibration, 0, sizeof(phCalibration));
}

// initialize sensors and load calibration
void HydroponicsController::begin()
{
    // setup relay pins
    for (int i = 0; i < NUM_RELAYS; i++)
    {
        pinMode(relayPins[i], OUTPUT);
        digitalWrite(relayPins[i], HIGH); // relays are active low
    }

    // setup pH sensor pins
    for (int i = 0; i < NUM_PH_SENSORS; i++)
    {
        pinMode(phPins[i], INPUT);
    }

    // initialize DHT sensor
    dht.begin();

    // load calibration from EEPROM
    loadCalibration();
}

// main update loop
void HydroponicsController::update()
{
    // check if it's time to sample sensors
    if (millis() - lastSampleTime >= SAMPLE_INTERVAL)
    {
        lastSampleTime = millis();

        // prepare sensor data
        SensorData data = SensorData_init_zero;
        getSensorData(data);

        // encode and send data over serial
        uint8_t buffer[128];
        pb_ostream_t stream = pb_ostream_from_buffer(buffer, sizeof(buffer));
        if (pb_encode(&stream, SensorData_fields, &data))
        {
            uint16_t message_length = stream.bytes_written;
            sendSensorData(buffer, message_length);
        }
        else
        {
            // encoding failed, handle error
        }
    }

    // check for incoming commands
    while (Serial.available() >= 2)
    {
        // Read the length prefix
        uint8_t length_bytes[2];
        Serial.readBytes(length_bytes, 2);
        uint16_t message_length = length_bytes[0] | (length_bytes[1] << 8);

        if (message_length > 128)
        {
            // Invalid message length, skip
            continue;
        }

        // Read the command data
        uint8_t buffer[128];
        size_t bytes_read = Serial.readBytes(buffer, message_length);
        if (bytes_read < message_length)
        {
            // Incomplete command, skip
            continue;
        }

        // Decode the command
        pb_istream_t stream = pb_istream_from_buffer(buffer, message_length);
        Command cmd = Command_init_zero;

        if (pb_decode(&stream, Command_fields, &cmd))
        {
            Serial.print("Received command of type: ");
            Serial.println(cmd.type);
            handleCommand(cmd);
        }
        else
        {
            // Serial.println("Failed to decode command");
        }
    }
}

// read all sensor data
void HydroponicsController::getSensorData(SensorData &data)
{
    data.temperature = dht.readTemperature();
    data.humidity = dht.readHumidity();
    data.light_level = readLightLevel();

    // Read pH sensors
    data.ph_levels_count = NUM_PH_SENSORS;
    for (size_t i = 0; i < NUM_PH_SENSORS; i++)
    {
        phLevels[i] = readPHSensor(i);
        data.ph_levels[i] = phLevels[i];
    }

    // Update relay states
    data.relay_states_count = NUM_RELAYS;
    for (size_t i = 0; i < NUM_RELAYS; i++)
    {
        relayStateBuffer[i] = relayStates[i];
        data.relay_states[i] = relayStateBuffer[i];
    }
}

// read a single pH sensor
float HydroponicsController::readPHSensor(uint8_t index)
{
    if (index >= NUM_PH_SENSORS)
    {
        return -1.0f; // Invalid sensor index
    }

    float sum = 0;
    int validReadings = 0;
    const int MIN_VALID_READINGS = 3; // Minimum readings required for valid result

    for (int i = 0; i < PH_SAMPLES; i++)
    {
        int rawValue = analogRead(phPins[index]);

        // Check for invalid/disconnected sensor readings
        if (rawValue == 0 || rawValue == 1023 || rawValue < 100)
        {
            continue; // Skip clearly invalid readings
        }

        float voltage = (float)rawValue * 5.0f / 1023.0f;

        // Validate voltage is in reasonable range (0.5V-4.5V typical for pH sensors)
        if (voltage < 0.5f || voltage > 4.5f)
        {
            continue;
        }

        float ph = 7.0f + ((2.5f - voltage) / 0.18f) * phCalibration[index];

        // Validate pH value is in reasonable range
        if (ph >= 0.0f && ph <= 14.0f)
        {
            sum += ph;
            validReadings++;
        }

        delay(10);
    }

    // Return -1 if we didn't get enough valid readings
    if (validReadings < MIN_VALID_READINGS)
    {
        return -1.0f;
    }

    return sum / validReadings;
}

// read light level
float HydroponicsController::readLightLevel()
{
    int rawValue = analogRead(LDR_PIN);
    return (float)rawValue * 100.0 / 1023.0;
}

// toggle relay state
void HydroponicsController::toggleRelay(uint32_t index)
{
    if (index >= NUM_RELAYS)
    {
        return; // Invalid index, silently return
    }

    // Add delay to prevent rapid switching that could damage relays
    static unsigned long lastToggleTime = 0;
    const unsigned long RELAY_TOGGLE_DELAY = 100; // 100ms minimum between toggles

    if (millis() - lastToggleTime < RELAY_TOGGLE_DELAY)
    {
        return; // Too soon to toggle again
    }

    // Toggle relay state
    relayStates[index] = !relayStates[index];

    // Relays are active low, so we invert the state
    digitalWrite(relayPins[index], !relayStates[index]);

    lastToggleTime = millis();
}

// calibrate pH sensor
void HydroponicsController::calibratePHSensor(uint32_t index, float value)
{
    // Validate index and calibration value
    if (index >= NUM_PH_SENSORS)
    {
        return; // Invalid sensor index
    }

    if (value <= 0 || value > 14)
    {
        return; // pH values must be between 0-14
    }

    // Take multiple readings to ensure stable value
    float sum = 0;
    int validReadings = 0;
    const int CALIBRATION_SAMPLES = 10;

    for (int i = 0; i < CALIBRATION_SAMPLES; i++)
    {
        float reading = readPHSensor(index);
        if (reading != -1.0f)
        {
            sum += reading;
            validReadings++;
        }
        delay(100); // Wait between readings
    }

    // Only calibrate if we got enough valid readings
    if (validReadings >= CALIBRATION_SAMPLES / 2)
    {
        float avgReading = sum / validReadings;
        if (avgReading != 0)
        {
            phCalibration[index] = value / avgReading;
            saveCalibration();
        }
    }
}

// load calibration data from EEPROM
void HydroponicsController::loadCalibration()
{
    for (int i = 0; i < NUM_PH_SENSORS; i++)
    {
        EEPROM.get(EEPROM_PH_OFFSET + (i * sizeof(float)), phCalibration[i]);
        if (isnan(phCalibration[i]) || phCalibration[i] <= 0)
        {
            phCalibration[i] = 1.0; // default calibration
        }
    }
}

// save calibration data to EEPROM
void HydroponicsController::saveCalibration()
{
    for (int i = 0; i < NUM_PH_SENSORS; i++)
    {
        EEPROM.put(EEPROM_PH_OFFSET + (i * sizeof(float)), phCalibration[i]);
    }
}

// handle incoming commands
void HydroponicsController::handleCommand(const Command &cmd)
{
    switch (cmd.type)
    {
    case Command_CommandType_TOGGLE_RELAY:
        toggleRelay(cmd.relay_index);
        break;
    case Command_CommandType_CALIBRATE_PH:
        calibratePHSensor(cmd.ph_sensor_index, cmd.ph_calibration_value);
        break;
    default:
        // Serial.println("Unknown command type");
        break;
    }
}

void HydroponicsController::sendSensorData(const uint8_t* buffer, uint16_t length) {
    Serial.write(0xFF);  // Start marker
    Serial.write(0xFE);
    Serial.write((uint8_t*)&length, 2);  // Length prefix
    Serial.write(buffer, length);
    Serial.write(0xFD);  // End marker
    Serial.write(0xFC);
}
#ifndef HYDROPONICS_H
#define HYDROPONICS_H

#include <Arduino.h>
#include <DHT.h>
#include <EEPROM.h>
#include "hydroponics.pb.h"

// pin definitions
#define DHT_PIN 2
#define LDR_PIN A0
#define PH_PINS {A1, A2, A3, A4, A5}
#define RELAY_PINS {3, 4, 5, 6, 7}

// constants
#define NUM_PH_SENSORS 5
#define NUM_RELAYS 5
#define SAMPLE_INTERVAL 1000 // 1 second
#define PH_SAMPLES 10
#define EEPROM_PH_OFFSET 0

class HydroponicsController
{
private:
    DHT dht;
    uint8_t phPins[NUM_PH_SENSORS];
    uint8_t relayPins[NUM_RELAYS];
    float phCalibration[NUM_PH_SENSORS];
    bool relayStates[NUM_RELAYS];
    unsigned long lastSampleTime;

    // sensor data buffers
    float phLevels[NUM_PH_SENSORS];
    bool relayStateBuffer[NUM_RELAYS];
    float lightLevel;

    // private methods
    float readPHSensor(uint8_t index);
    float readLightLevel();
    void loadCalibration();
    void saveCalibration();
    void getSensorData(SensorData &data);
    void handleCommand(const Command &cmd);
    void sendSensorData(const uint8_t* buffer, uint16_t length);
public:
    HydroponicsController();
    void begin();
    void update();
    void toggleRelay(uint32_t index);
    void calibratePHSensor(uint32_t index, float value);
};

#endif
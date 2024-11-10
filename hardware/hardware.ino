#include "hydroponics.h"

HydroponicsController hydroponics;

void setup() {
    Serial.begin(9600);
    hydroponics.begin();
}

void loop() {
    hydroponics.update();
}
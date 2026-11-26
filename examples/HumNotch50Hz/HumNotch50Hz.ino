/*
 * HumNotch50Hz: remove 50 Hz mains hum from an analog input with a notch filter
 * (sampling rate 1000 Hz, quality factor 30).
 *
 * notch50.h was generated on a PC with:
 *     filter2c notch --freq 50 --q 30 --fs 1000 --name notch50 -o notch50.h --write-runtime
 * In countries with 60 Hz mains, generate it with --freq 60 instead.
 *
 * Wiring, no extra parts: push one jumper wire into the pin below and leave the
 * other end free in the air. A free wire acts as a small antenna and picks up
 * the hum from nearby mains wiring and chargers. Touching the bare end with a
 * finger usually makes the hum stronger. How much you see depends on your
 * surroundings, and an ESP32 analog input is noisy by itself.
 *
 * Open the Serial Plotter at 921600 baud (the baud rate is ignored on a native
 * USB port). It draws two lines, both with the slow average removed:
 *     raw   the signal as the pin sees it
 *     notch the same signal after the 50 Hz notch filter
 */
#include <Arduino.h>

#include "filter2c.h"
#include "notch50.h"

const int ADC_PIN = 1;                        // GPIO1 on ESP32-S3 boards, change for your board
const unsigned long SAMPLE_PERIOD_US = 1000;  // 1000 Hz, must match --fs

static unsigned long nextSampleUs;
static float average = 0.0f;
static bool haveAverage = false;

void setup()
{
    Serial.begin(921600);
    filter2c_reset(&notch50);
    nextSampleUs = micros();
}

void loop()
{
    // Wait for the next sample time. The subtraction also works when micros() wraps around.
    if ((long)(micros() - nextSampleUs) < 0) {
        return;
    }
    nextSampleUs += SAMPLE_PERIOD_US;

    float raw = (float)analogRead(ADC_PIN);
    float clean = filter2c_process(&notch50, raw);

    // Follow the slow average (about 1 second) so the plot is centred on zero.
    if (!haveAverage) {
        average = raw;
        haveAverage = true;
    }
    average += 0.001f * (raw - average);

    Serial.printf("raw:%.1f,notch:%.1f\n", (double)(raw - average), (double)(clean - average));
}

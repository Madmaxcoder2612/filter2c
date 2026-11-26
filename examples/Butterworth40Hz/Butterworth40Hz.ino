/*
 * Butterworth40Hz: smooth an analog signal with a 4th-order Butterworth
 * low-pass filter (cutoff 40 Hz) sampled at 1000 Hz.
 *
 * lp40.h was generated on a PC with:
 *     filter2c butter-lowpass --order 4 --cutoff 40 --fs 1000 --name lp40 -o lp40.h
 *
 * Wiring: a sensor or signal source on analog pin A0.
 * Open the Serial Plotter at 921600 baud (the speed is ignored on a native USB
 * port) to see the raw and the filtered signal. A lower baud rate cannot carry
 * 1000 lines per second, the loop would fall behind and the filter would no
 * longer run at 1000 Hz.
 */
#include "lp40.h"

const unsigned long SAMPLE_PERIOD_US = 1000;  // 1000 Hz, must match --fs

unsigned long nextSampleUs;

void setup()
{
    Serial.begin(921600);
    filter2c_reset(&lp40);
    nextSampleUs = micros();
}

void loop()
{
    // Wait for the next sample time. The subtraction also works when micros() wraps around.
    if ((long)(micros() - nextSampleUs) < 0) {
        return;
    }
    nextSampleUs += SAMPLE_PERIOD_US;

    float raw = (float)analogRead(A0);
    float smooth = filter2c_process(&lp40, raw);

    // "name:value" pairs make the Serial Plotter label the two lines.
    Serial.print("raw:");
    Serial.print((int)raw);
    Serial.print(",smooth:");
    Serial.println(smooth, 1);
}

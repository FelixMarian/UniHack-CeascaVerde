// Values in centimetres. User-selected thresholds; verify on the physical bin.
// A lateral sensor detects waste when distance <= its threshold.
#define MID_DETECT_CM 5
#define FULL_DETECT_CM 5
// Independent confirmation limits for the state detected by the lateral sensor.
#define TOP_FULL_CM 5
#define TOP_MEDIUM_CM 10
// Software sanity range, not a claim about hardware measurement accuracy.
// Adjust to the actual sensor model. Zero/no-echo is always invalid.
#define SENSOR_MIN_CM 0.1
#define SENSOR_MAX_CM 400

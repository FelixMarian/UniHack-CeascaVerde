// Values in centimetres. User-selected thresholds; verify on the physical bin.
// A lateral sensor detects waste when distance <= its threshold.
#define MID_DETECT_CM 15
#define FULL_DETECT_CM 15
// Independent confirmation limits for the state detected by the lateral sensor.
#define TOP_FULL_CM 10
#define TOP_MEDIUM_CM 50
// Software sanity range, not a claim about hardware measurement accuracy.
// Adjust to the actual sensor model. Zero/no-echo is always invalid.
#define SENSOR_MIN_CM 0.1
#define SENSOR_MAX_CM 400

/*
 * calibration_detecteurs.ino
 * ==========================
 * Applies the gain/offset correction factors computed by
 * calibration_detectors.py to the three log-detector channels
 * VA, VG, V+ of the TEXTOR ICRH AMD.
 *
 * V_corr = GAIN_CORR * V_raw + OFFSET_CORR
 *
 * Goal: bring VA and V+ onto the scale of VG (reference channel),
 * so that the three V(P_dBm) "lines" overlap before computing
 * eps_a / eps_g in neutral_point.ino.
 *
 */

// ---------------------------------------------------------------
// ADC pins
// ---------------------------------------------------------------
const int PIN_VA    = A0;
const int PIN_VG    = A1;
const int PIN_VPLUS = A2;

// ---------------------------------------------------------------
// ADC reference (Arduino Uno, DEFAULT = Vcc ~5V, resolution 10 bits)
// ---------------------------------------------------------------
const float ADC_VREF = 5.0f;
const float ADC_MAX  = 1023.0f;

// ---------------------------------------------------------------
// Correction factors (from calibration_detectors.py)
// Reference = VG  ->  VG_GAIN_CORR = 1, VG_OFFSET_CORR = 0
// ---------------------------------------------------------------
const float VA_GAIN_CORR      = 1.02846f;
const float VA_OFFSET_CORR    = -0.01242f;

const float VG_GAIN_CORR      = 1.00000f;
const float VG_OFFSET_CORR    = 0.00000f;

const float VPLUS_GAIN_CORR   = 1.16427f;
const float VPLUS_OFFSET_CORR = -0.81718f;

// ---------------------------------------------------------------
// Number of samples averaged per measurement cycle
// ---------------------------------------------------------------
const int NB_SAMPLES = 100;

// ---------------------------------------------------------------
// Raw ADC reading -> voltage (V), no correction applied
// ---------------------------------------------------------------
float readRawVoltage(int pin) {
  int raw = analogRead(pin);
  return (raw * ADC_VREF) / ADC_MAX;
}

// ---------------------------------------------------------------
// Corrected voltages (gain + offset) for each channel
// ---------------------------------------------------------------
float readVA_corrected() {
  float v_brut = readRawVoltage(PIN_VA);
  return VA_GAIN_CORR * v_brut + VA_OFFSET_CORR;
}

float readVG_corrected() {
  float v_brut = readRawVoltage(PIN_VG);
  return VG_GAIN_CORR * v_brut + VG_OFFSET_CORR;
}

float readVPlus_corrected() {
  float v_brut = readRawVoltage(PIN_VPLUS);
  return VPLUS_GAIN_CORR * v_brut + VPLUS_OFFSET_CORR;
}

// ---------------------------------------------------------------
// Measurement cycle: average over NB_SAMPLES, raw + corrected
// ---------------------------------------------------------------
void runMeasurementCycle() {
  float sumVA_raw = 0, sumVG_raw = 0, sumVP_raw = 0;
  float sumVA_cor = 0, sumVG_cor = 0, sumVP_cor = 0;

  Serial.println(F("Nouveau cycle demarre -- prise de mesures..."));

  for (int i = 0; i < NB_SAMPLES; i++) {
    float va_raw = readRawVoltage(PIN_VA);
    float vg_raw = readRawVoltage(PIN_VG);
    float vp_raw = readRawVoltage(PIN_VPLUS);

    float va_cor = VA_GAIN_CORR * va_raw + VA_OFFSET_CORR;
    float vg_cor = VG_GAIN_CORR * vg_raw + VG_OFFSET_CORR;
    float vp_cor = VPLUS_GAIN_CORR * vp_raw + VPLUS_OFFSET_CORR;

    sumVA_raw += va_raw;
    sumVG_raw += vg_raw;
    sumVP_raw += vp_raw;
    sumVA_cor += va_cor;
    sumVG_cor += vg_cor;
    sumVP_cor += vp_cor;

    delay(5);  // petit delai entre echantillons
  }

  float VA_moy_raw = sumVA_raw / NB_SAMPLES;
  float VG_moy_raw = sumVG_raw / NB_SAMPLES;
  float VP_moy_raw = sumVP_raw / NB_SAMPLES;
  float VA_moy_cor = sumVA_cor / NB_SAMPLES;
  float VG_moy_cor = sumVG_cor / NB_SAMPLES;
  float VP_moy_cor = sumVP_cor / NB_SAMPLES;

  Serial.println(F("=== Average over the measurements taken ==="));
  Serial.print(F("Number of samples: "));
  Serial.println(NB_SAMPLES);

  Serial.println(F("--- Raw (before correction) ---"));
  Serial.print(F("VA_avg    = ")); Serial.print(VA_moy_raw, 4); Serial.println(F(" V"));
  Serial.print(F("VG_avg    = ")); Serial.print(VG_moy_raw, 4); Serial.println(F(" V"));
  Serial.print(F("Vplus_avg = ")); Serial.print(VP_moy_raw, 4); Serial.println(F(" V"));

  Serial.println(F("--- Corrected (gain/offset applied) ---"));
  Serial.print(F("VA_avg    = ")); Serial.print(VA_moy_cor, 4); Serial.println(F(" V"));
  Serial.print(F("VG_avg    = ")); Serial.print(VG_moy_cor, 4); Serial.println(F(" V"));
  Serial.print(F("Vplus_avg = ")); Serial.print(VP_moy_cor, 4); Serial.println(F(" V"));
  Serial.println(F("======================================="));
}

void setup() {
  Serial.begin(115200);
  Serial.println(F("VA/VG/V+ calibration -- send anything to start a cycle."));
}

void loop() {
  if (Serial.available() > 0) {
    while (Serial.available() > 0) Serial.read();  // clear the buffer
    runMeasurementCycle();
    Serial.println(F("Send anything to start a new measurement cycle."));
  }
}
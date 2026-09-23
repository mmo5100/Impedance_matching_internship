/*
 * Streams V+ and VA continuously over serial.
 *
 * VA is duplicated on BOTH the Arduino and the LabJack (LabJack AIN0),
 * so the PC-side merge script can directly compare the readings and
 * flag any mismatch -- a strong signal of clock drift/synchronization
 * issues between the two independently-timed data sources, not just a
 * calibration difference. (Unlike the LabJack, the Arduino has no fixed
 * channel budget for extra streamed signals -- each one is just another
 * analogRead() in the same loop.)
 *
 * VA, VG, position_Ca, and position_Cg all live on the LabJack (bipolar
 * +-10V inputs), since BOTH positions can be negative. V+ has no spare
 * LabJack channel left, so it stays solely on the Arduino (confirmed to
 * remain positive, no clipping risk on the unipolar 0-5V ADC) and is
 * merged in on the PC side for the eps_a/eps_g calculation.
 *
 * CALIBRATION: VA and V+ readings go through the same gain/offset
 * detector correction used elsewhere (from calibration_detectors.py),
 * V_corr = GAIN_CORR * V_brut + OFFSET_CORR, so the Arduino-side value
 * is directly comparable to the LabJack's (uncalibrated, direct volt
 * reading) value in the cross-check.
 *
 * OUTPUT FORMAT (for the PC-side merge script), each on its own line :
 *   - '#'      prefix -> human-readable comments, ignore.
 *   - 'VPLUS'  prefix -> VPLUS,value
 *   - 'VA'     prefix -> VA,value
 *
 * Wiring: V+ -> A2   VA -> A0
 */

const int PIN_VPLUS = A2;
const int PIN_VA    = A0;

// Correction factors (from calibration_detectors.py)
// V_corr = GAIN_CORR * V_brut + OFFSET_CORR
const double VA_GAIN_CORR      = 1.02846;
const double VA_OFFSET_CORR    = -0.01242;

const double VPLUS_GAIN_CORR   = 1.16427;
const double VPLUS_OFFSET_CORR = -0.81718;

const double ADC_REF_V = 4.697;
const double ADC_MAX   = 1023.0;

const unsigned long PERIODE_MS = 50;  // streaming period
unsigned long t_last = 0;

void setup() {
  Serial.begin(115200);
  Serial.println(F("# Streaming V+ (A2) and VA (A0) continuously, with detector calibration applied..."));
}

double readProbeVolts(int pin, double gain, double offset) {
  int raw = analogRead(pin);
  double v_adc = (raw / ADC_MAX) * ADC_REF_V;
  return v_adc * gain + offset;
}

void loop() {
  unsigned long t_now = millis();
  if (t_now - t_last < PERIODE_MS) return;
  t_last = t_now;

  double Vplus = readProbeVolts(PIN_VPLUS, VPLUS_GAIN_CORR, VPLUS_OFFSET_CORR);
  double VA    = readProbeVolts(PIN_VA,    VA_GAIN_CORR,    VA_OFFSET_CORR);

  Serial.print(F("VPLUS,"));
  Serial.println(Vplus, 6);
  Serial.print(F("VA,"));
  Serial.println(VA, 6);
}
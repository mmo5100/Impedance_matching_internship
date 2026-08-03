/*
 * Voltage sweep (v_a/v_g) -- OPEN-loop search for the combination
 * that minimizes the error (eps_a, eps_g).
 *
 * PRINCIPLE:
 *   1) Coarse pass: sweep an NxN grid of (v_a_real, v_g_real) over the
 *      full range [V_REEL_MIN, V_REEL_MAX], wait for settling
 *      (SETTLE_MS) at each point, measure eps_a/eps_g, and compute an
 *      overall error err = sqrt(eps_a^2 + eps_g^2). Keep the point
 *      (v_a, v_g) that minimizes err.
 *   2) Fine pass: sweep a finer grid, centered on the best point
 *      found, within a narrower window.
 *   3) Then hold the best point found (end of the 2nd pass)
 *      continuously, displaying eps_a/eps_g to check stability.
 */

#include <math.h>
#include "DFRobot_GP8403.h"

// ---------------------------------------------------------------------------
// Mapping VA/VG <-> l1/l2
// ---------------------------------------------------------------------------
const bool SWAP_VA_VG = false;

// ---------------------------------------------------------------------------
// RF parameters
// ---------------------------------------------------------------------------
const double FREQ_HZ = 28e6;
const double C_LIGHT = 299792458.0;
const double L1_M    = 1.35;
const double L2_M    = 1.85;
const double BETA    = 2.0 * PI * FREQ_HZ / C_LIGHT;
double sin2bl1, cos2bl1, sin2bl2, cos2bl2;

// ---------------------------------------------------------------------------
// Analog inputs
// ---------------------------------------------------------------------------
const int PIN_VPLUS = A2;
const int PIN_VA    = A0;
const int PIN_VG    = A1;

// Correction factors (from calibration_detectors.py)
// V_corr = GAIN_CORR * V_brut + OFFSET_CORR
const double VA_GAIN_CORR      = 1.02846;
const double VA_OFFSET_CORR    = -0.01242;

const double VG_GAIN_CORR      = 1.00000;
const double VG_OFFSET_CORR    = 0.00000;

const double VPLUS_GAIN_CORR   = 1.16427;
const double VPLUS_OFFSET_CORR = -0.81718;



const double ADC_REF_V   = 5.0;
const double ADC_MAX     = 1023.0;

// ---------------------------------------------------------------------------
// DAC GP8403
// ---------------------------------------------------------------------------
#define ADRESSE_I2C_DAC 0x5F
DFRobot_GP8403 dac(&Wire, ADRESSE_I2C_DAC);

const int CANAL_CA = 0;   // Vout0 -> Ca (ANTENNA side)
const int CANAL_CG = 1;   // Vout1 -> Cg (GENERATOR side)

const double DAC_VREF_V    = 10.0;
const double OFFSET_PILE_V = 3.0;
const double V_REEL_MIN = -OFFSET_PILE_V;            // -3.0 V -> v_dac=0V  (DAC limit)
const double V_REEL_MAX = DAC_VREF_V - OFFSET_PILE_V; // +7.0 V -> v_dac=10V (DAC limit)

// Requested sweep range (narrower than the hardware range above):
const double V_SWEEP_MIN = -0.85;   // V
const double V_SWEEP_MAX = 0.85;    // V



// ---------------------------------------------------------------------------
// Sweep parameters
// ---------------------------------------------------------------------------
const int    N_COARSE       = 9;     // NxN grid (coarse pass)
const int    N_FINE         = 9;     // NxN grid (fine pass)
const double FINE_WINDOW_V  = 0.2;   // +/- V around the best point, fine pass
const unsigned long SETTLE_MS = 300; // wait time after each command


// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  sin2bl1 = sin(2.0 * BETA * L1_M);
  cos2bl1 = cos(2.0 * BETA * L1_M);
  sin2bl2 = sin(2.0 * BETA * L2_M);
  cos2bl2 = cos(2.0 * BETA * L2_M);

  Serial.println(F("Initializing GP8403 DAC..."));
  while (dac.begin() != 0) {
    Serial.println(F("  Init error -- check I2C wiring and address."));
    delay(1000);
  }
  dac.setDACOutRange(dac.eOutputRange10V);
  Serial.println(F("DAC initialized successfully."));

  double bestA, bestG, bestErr;

  Serial.println(F("=== Coarse pass ==="));
  balayerGrille(V_SWEEP_MIN, V_SWEEP_MAX, V_SWEEP_MIN, V_SWEEP_MAX, N_COARSE, bestA, bestG, bestErr);
  Serial.print(F(">>> Best point (coarse): v_a=")); Serial.print(bestA, 3);
  Serial.print(F(" v_g=")); Serial.print(bestG, 3);
  Serial.print(F(" err=")); Serial.println(bestErr, 4);

  double loA = max(V_SWEEP_MIN, bestA - FINE_WINDOW_V);
  double hiA = min(V_SWEEP_MAX, bestA + FINE_WINDOW_V);
  double loG = max(V_SWEEP_MIN, bestG - FINE_WINDOW_V);
  double hiG = min(V_SWEEP_MAX, bestG + FINE_WINDOW_V);

  Serial.println(F("=== Fine pass ==="));
  balayerGrille(loA, hiA, loG, hiG, N_FINE, bestA, bestG, bestErr);
  Serial.print(F(">>> Best point (fine): v_a=")); Serial.print(bestA, 3);
  Serial.print(F(" v_g=")); Serial.print(bestG, 3);
  Serial.print(F(" err=")); Serial.println(bestErr, 4);

  Serial.println(F("=== Holding the best point found ==="));
  outputTensionReelle(bestA, CANAL_CA);
  outputTensionReelle(bestG, CANAL_CG);
}

// ---------------------------------------------------------------------------
double readProbeVolts(int pin, double gain, double offset) {
  int raw = analogRead(pin);
  double v_adc = (raw / ADC_MAX) * ADC_REF_V;
  return v_adc * gain + offset;
}

void outputTensionReelle(double v_reel, int canal) {
  double v_dac = constrain(v_reel + OFFSET_PILE_V, 0.0, DAC_VREF_V);
  dac.setDACOutVoltage((int)(v_dac * 1000.0), canal);
}

// Measures eps_a, eps_g at the current command (v_a_real, v_g_real), after
// settling.
void mesurerEps(double v_a_reel, double v_g_reel, double &eps_a, double &eps_g) {
  outputTensionReelle(v_a_reel, CANAL_CA);
  outputTensionReelle(v_g_reel, CANAL_CG);
  delay(SETTLE_MS);

  double Vplus = readProbeVolts(PIN_VPLUS, VPLUS_GAIN_CORR, VPLUS_OFFSET_CORR);
  double VA    = readProbeVolts(PIN_VA,    VA_GAIN_CORR, VA_OFFSET_CORR);
  double VG    = readProbeVolts(PIN_VG,    VG_GAIN_CORR, VG_OFFSET_CORR);

  double VA_minus_Vp = VA - Vplus;
  double VG_minus_Vp = VG - Vplus;

  double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;
  double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;

  eps_a = sVA * sin2bl2 - sVG * sin2bl1;
  eps_g = sVA * cos2bl2 - sVG * cos2bl1;
}

// Sweeps an NxN grid over [loA,hiA] x [loG,hiG], in a serpentine pattern
// (to limit voltage jumps between consecutive points), prints each
// measurement, and returns the best point (minimum error).

void balayerGrille(double loA, double hiA, double loG, double hiG, int n,
                    double &bestA, double &bestG, double &bestErr) {
  bestErr = 1e18;
  bestA = loA;
  bestG = loG;

  double stepA = (n > 1) ? (hiA - loA) / (n - 1) : 0.0;
  double stepG = (n > 1) ? (hiG - loG) / (n - 1) : 0.0;

  for (int i = 0; i < n; i++) {
    double v_a = loA + i * stepA;
    bool sensDirect = (i % 2 == 0);
    for (int jj = 0; jj < n; jj++) {
      int j = sensDirect ? jj : (n - 1 - jj);
      double v_g = loG + j * stepG;

      double eps_a, eps_g;
      mesurerEps(v_a, v_g, eps_a, eps_g);
      double err = sqrt(eps_a * eps_a + eps_g * eps_g);

      Serial.print(F("v_a=")); Serial.print(v_a, 3);
      Serial.print(F(" v_g=")); Serial.print(v_g, 3);
      Serial.print(F(" eps_a=")); Serial.print(eps_a, 4);
      Serial.print(F(" eps_g=")); Serial.print(eps_g, 4);
      Serial.print(F(" err=")); Serial.print(err, 4);

      if (err < bestErr) {
        bestErr = err;
        bestA = v_a;
        bestG = v_g;
        Serial.print(F("  <-- new minimum"));
      }
      Serial.println();
    }
  }
}

// ---------------------------------------------------------------------------
void loop() {
  // The sweep runs only once, in setup(). Here we hold the best point
  // found, displaying eps_a/eps_g to check stability (useful to see
  // whether the error stays low over time).
  static unsigned long t_last = 0;
  if (millis() - t_last > 500) {
    t_last = millis();
    double Vplus = readProbeVolts(PIN_VPLUS, VPLUS_GAIN_CORR, VPLUS_OFFSET_CORR);
    double VA    = readProbeVolts(PIN_VA,    VA_GAIN_CORR,    VA_OFFSET_CORR);
    double VG    = readProbeVolts(PIN_VG,    VG_GAIN_CORR,    VG_OFFSET_CORR);
    double VA_minus_Vp = VA - Vplus;
    double VG_minus_Vp = VG - Vplus;
    double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;
    double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;
    double eps_a = sVA * sin2bl2 - sVG * sin2bl1;
    double eps_g = sVA * cos2bl2 - sVG * cos2bl1;
    Serial.print(F("[holding] eps_a=")); Serial.print(eps_a, 4);
    Serial.print(F(" eps_g=")); Serial.println(eps_g, 4);
  }
}
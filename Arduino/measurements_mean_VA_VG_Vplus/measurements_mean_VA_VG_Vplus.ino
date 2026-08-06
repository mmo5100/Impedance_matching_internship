/*
 * Continuous measurement of VA, VG, V+, position_Ca, position_Cg --
 * eps_a/eps_g computed alongside. NO DAC, NO voltage command, just
 * reading + computation.
 *
 * Takes exactly N_ECHANTILLONS measurements, stops on its own, prints the
 * AVERAGE of these N_ECHANTILLONS measurements, then WAITS for anything
 * to be sent over the Serial Monitor (Enter is enough) to start a new
 * cycle of N_ECHANTILLONS measurements.
 *
 * OUTPUT FORMAT (for logging to CSV from a PC script) :
 *   - Lines starting with '#'    -> human-readable comments/status, ignore.
 *   - Lines starting with 'DATA' -> DATA,cycle,sample_index,VA,VG,Vplus,eps_a,eps_g,position_Ca,position_Cg
 *   - Lines starting with 'AVG'  -> AVG,cycle,n_samples,VA_avg,VG_avg,Vplus_avg,eps_a_avg,eps_g_avg,position_Ca_avg,position_Cg_avg
 *
 * Probe wiring: identical to neutral_point.ino, plus 2 extra channels:
 *   V+          -> A2
 *   VA          -> A0
 *   VG          -> A1
 *   position_Ca -> A3
 *   position_Cg -> A4
 */

#include <math.h>

// ---------------------------------------------------------------------------
// Mapping VA/VG <-> l1/l2 (identical to neutral_point.ino)
// ---------------------------------------------------------------------------
const bool SWAP_VA_VG = false;

// ---------------------------------------------------------------------------
// RF parameters
// ---------------------------------------------------------------------------
const double FREQ_HZ = 38e6;
const double C_LIGHT = 299792458.0;
const double L1_M    = 1.35;
const double L2_M    = 1.85;
const double BETA    = 2.0 * PI * FREQ_HZ / C_LIGHT;
double sin2bl1, cos2bl1, sin2bl2, cos2bl2;

// ---------------------------------------------------------------------------
// Analog inputs (identical to neutral_point.ino, plus the 2 position channels)
// ---------------------------------------------------------------------------
const int PIN_VPLUS       = A2;
const int PIN_VA          = A0;
const int PIN_VG          = A1;
const int PIN_POSITION_CA = A3;   // <-- adjust pin if wired differently
const int PIN_POSITION_CG = A4;   // <-- adjust pin if wired differently

const double VPLUS_SCALE       = 1.0;
const double VA_SCALE          = 1.0;
const double VG_SCALE          = 1.0;
const double POSITION_CA_SCALE = 1.0;  // TODO: set to the real V->mm calibration if known
const double POSITION_CG_SCALE = 1.0;  // TODO: set to the real V->mm calibration if known
const double ADC_REF_V   = 5.0;
const double ADC_MAX     = 1023.0;

const unsigned long PERIODE_ECHANTILLON_MS = 20;  // sampling period
const int N_ECHANTILLONS = 100;                   // samples per cycle

// ---------------------------------------------------------------------------
// Sketch state
// ---------------------------------------------------------------------------
enum EtatMesure { EN_COURS, ARRETE };
EtatMesure etat = EN_COURS;

int cycleNumber = 1;

// Accumulators
double sumVA = 0.0, sumVG = 0.0, sumVplus = 0.0;
double sumEpsA = 0.0, sumEpsG = 0.0;
double sumPositionCa = 0.0, sumPositionCg = 0.0;
int nEch = 0;
unsigned long t_dernier_echantillon = 0;

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  sin2bl1 = sin(2.0 * BETA * L1_M);
  cos2bl1 = cos(2.0 * BETA * L1_M);
  sin2bl2 = sin(2.0 * BETA * L2_M);
  cos2bl2 = cos(2.0 * BETA * L2_M);

  Serial.println(F("# Measuring VA, VG, V+, position_Ca, position_Cg -- eps_a, eps_g"));
  Serial.print(F("# Cycle "));
  Serial.print(cycleNumber);
  Serial.print(F(": taking "));
  Serial.print(N_ECHANTILLONS);
  Serial.println(F(" samples..."));

  reinitialiserAccumulateurs();
}

// ---------------------------------------------------------------------------
double readProbeVolts(int pin, double scale) {
  int raw = analogRead(pin);
  double v_adc = (raw / ADC_MAX) * ADC_REF_V;
  return v_adc * scale;
}

void reinitialiserAccumulateurs() {
  sumVA = 0.0; sumVG = 0.0; sumVplus = 0.0;
  sumEpsA = 0.0; sumEpsG = 0.0;
  sumPositionCa = 0.0; sumPositionCg = 0.0;
  nEch = 0;
}

void afficherMoyenne() {
  Serial.print(F("AVG,"));
  Serial.print(cycleNumber); Serial.print(F(","));
  Serial.print(nEch); Serial.print(F(","));
  if (nEch == 0) {
    Serial.println(F("nan,nan,nan,nan,nan,nan,nan"));
  } else {
    Serial.print(sumVA          / nEch, 6); Serial.print(F(","));
    Serial.print(sumVG          / nEch, 6); Serial.print(F(","));
    Serial.print(sumVplus       / nEch, 6); Serial.print(F(","));
    Serial.print(sumEpsA        / nEch, 6); Serial.print(F(","));
    Serial.print(sumEpsG        / nEch, 6); Serial.print(F(","));
    Serial.print(sumPositionCa  / nEch, 6); Serial.print(F(","));
    Serial.println(sumPositionCg / nEch, 6);
  }
  Serial.println(F("# Send anything (Enter) to start a new measurement cycle."));
}

// ---------------------------------------------------------------------------
void loop() {
  if (etat == ARRETE) {
    // Wait for a request to start a new cycle
    if (Serial.available()) {
      while (Serial.available()) Serial.read();  // flush input buffer
      cycleNumber++;
      reinitialiserAccumulateurs();
      etat = EN_COURS;
      Serial.print(F("# Cycle "));
      Serial.print(cycleNumber);
      Serial.print(F(" started -- taking "));
      Serial.print(N_ECHANTILLONS);
      Serial.println(F(" samples..."));
    }
    return;
  }

  // --- EN_COURS state: sample until N_ECHANTILLONS is reached ---
  unsigned long t_now = millis();
  if (t_now - t_dernier_echantillon < PERIODE_ECHANTILLON_MS) return;
  t_dernier_echantillon = t_now;

  double Vplus       = readProbeVolts(PIN_VPLUS,       VPLUS_SCALE);
  double VA          = readProbeVolts(PIN_VA,          VA_SCALE);
  double VG          = readProbeVolts(PIN_VG,          VG_SCALE);
  double positionCa  = readProbeVolts(PIN_POSITION_CA, POSITION_CA_SCALE);
  double positionCg  = readProbeVolts(PIN_POSITION_CG, POSITION_CG_SCALE);

  double VA_minus_Vp = VA - Vplus;
  double VG_minus_Vp = VG - Vplus;

  double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;
  double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;

  double eps_a = sVA * sin2bl2 - sVG * sin2bl1;
  double eps_g = sVA * cos2bl2 - sVG * cos2bl1;

  sumVA         += VA;
  sumVG         += VG;
  sumVplus      += Vplus;
  sumEpsA       += eps_a;
  sumEpsG       += eps_g;
  sumPositionCa += positionCa;
  sumPositionCg += positionCg;
  nEch++;

  Serial.print(F("DATA,"));
  Serial.print(cycleNumber); Serial.print(F(","));
  Serial.print(nEch); Serial.print(F(","));
  Serial.print(VA, 6); Serial.print(F(","));
  Serial.print(VG, 6); Serial.print(F(","));
  Serial.print(Vplus, 6); Serial.print(F(","));
  Serial.print(eps_a, 6); Serial.print(F(","));
  Serial.print(eps_g, 6); Serial.print(F(","));
  Serial.print(positionCa, 6); Serial.print(F(","));
  Serial.println(positionCg, 6);

  if (nEch >= N_ECHANTILLONS) {
    afficherMoyenne();
    etat = ARRETE;
  }
}

import pandas as pd
import sys

fichier = sys.argv[1] if len(sys.argv) > 1 else "mesures_63.17.csv"

df = pd.read_csv(fichier)

print(f"Fichier : {fichier}")
print(f"Nombre de points : {len(df)}")
print(f"\nMoyenne AIN0 : {df['AIN0'].mean():.6f} V")
print(f"Moyenne AIN2 : {df['AIN2'].mean():.6f} V")
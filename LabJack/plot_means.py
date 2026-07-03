import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import interp1d

lst_AIN0 = [-7.596508, -7.113932, -5.745318, -4.313887, -2.199152, -0.831050, -0.260090, 1.129560, 3.125149, 4.624997, 6.002058, 7.371470, 8.147502]
lst_AIN2 = [-0.002962, -0.003365, -0.004052, 0.002102, -0.004141, -0.004042, -0.003292, 0.007136, -0.004131, -0.004152, -0.004005, 0.007296, -0.003166]

x = np.array(lst_AIN0)
y = np.array(lst_AIN2)

idx = np.argsort(x)
x, y = x[idx], y[idx]

f        = interp1d(x, y, kind='cubic')
x_interp = np.linspace(x.min(), x.max(), 500)

plt.figure(figsize=(8, 5))
plt.scatter(x, y, color='tab:blue', s=30, label='Données')
plt.plot(x_interp, f(x_interp), color='tab:red', lw=1.5, label='Interpolation cubique')
plt.xlabel('AIN0 — Position [V]')
plt.ylabel('AIN2 — Courant [V]')
plt.title('Courant en fonction de la position')
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
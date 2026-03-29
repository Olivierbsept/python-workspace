import numpy as np
import matplotlib.pyplot as plt

# =============================
# FONCTIONS
# =============================
def compute_x012(A, B, D, E, M, depth=3):
    xs = []
    for _ in range(depth):
        C = (A + B) / 2
        F = (A + D) / 2
        H = (D + E) / 2
        G = (E + B) / 2

        AB = B - A
        AD = D - A
        DE = E - D
        EB = B - E

        if A <= M <= D:
            x_digit = 0
            M = C + (M - F) * AB / AD
        elif D < M <= E:
            x_digit = 1
            M = C + (M - H) * AB / DE
        else:
            x_digit = 2
            M = C + (M - G) * AB / EB

        xs.append(x_digit)
    return xs

def digits_to_float(digits):
    y = 0
    for i, d in enumerate(digits):
        y += d / (3 ** (i + 1))
    return y

def transform(x, fd_fraction, df_fraction, depth=9):
    digits = compute_x012(0, 1, fd_fraction, df_fraction, x, depth)
    return digits_to_float(digits)

# =============================
# PARAMÈTRES
# =============================
fd_fraction = 0.25
df_initial = 0.75
depth = 9

# =============================
# ÉCHANTILLONNAGE
# =============================
xs = np.linspace(0, 1, 500)
dx = xs[1] - xs[0]

# --- 1) df_fraction constante ---
df_const = np.full_like(xs, df_initial)
ys_const = np.array([transform(x, fd_fraction, df, depth) for x, df in zip(xs, df_const)])
dys_const = np.diff(ys_const) / dx
xs_mid = xs[:-1]

# --- 2) df_fraction variante (pièce par pièce) ---
df_piecewise = np.zeros_like(xs)
for i, x in enumerate(xs):
    if x <= fd_fraction:
        df_piecewise[i] = df_initial
    else:
        df_piecewise[i] = df_initial + (1 - df_initial) * (x - fd_fraction) / (1 - fd_fraction)

ys_piecewise = np.array([transform(x, fd_fraction, df, depth) for x, df in zip(xs, df_piecewise)])
dys_piecewise = np.diff(ys_piecewise) / dx

# =============================
# GRAPHE
# =============================
plt.figure(figsize=(12,6))

# --- Subplot 1 : y(x) ---
plt.subplot(2,1,1)
plt.plot(xs, ys_const, color='blue', label='y(x), df_fraction constante')
plt.plot(xs, ys_piecewise, color='green', label='y2(x), df_fraction pièce par pièce')
plt.xlabel("x")
plt.ylabel("y(x)")
plt.title("Fonctions y(x) en base 3")
plt.grid(True)
plt.legend()

# Graduation régulière en base 3
num_ticks = 10
yticks = np.linspace(0, 1, num_ticks)
def float_to_base3(y, depth=5):
    s = "0."
    for _ in range(depth):
        y *= 3
        digit = int(y)
        s += str(digit)
        y -= digit
    if y > 0:
        s += "…"
    return s
yticklabels = [float_to_base3(y) for y in yticks]
plt.yticks(yticks, yticklabels)

# --- Subplot 2 : y'(x) ---
plt.subplot(2,1,2)
plt.plot(xs_mid, dys_const, color='blue', label="y'(x), df_fraction constante")
plt.plot(xs_mid, dys_piecewise, color='green', label="y2'(x), df_fraction pièce par pièce")
plt.xlabel("x")
plt.ylabel("y'(x)")
plt.title("Dérivées numériques")
plt.grid(True)
plt.legend()

plt.tight_layout()
plt.show()
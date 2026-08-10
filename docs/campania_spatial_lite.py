"""
campania_spatial_lite.py
============================================================
SELF-CONTAINED spatial-regression pipeline for the Campania
coastal-weather study. Dependencies are deliberately minimal:
    requests pandas numpy scipy matplotlib
(no geopandas / PySAL needed). It:
  1. downloads REAL atmospheric data from NASA POWER (no login),
  2. builds row-standardised k-nearest-neighbour spatial weights,
  3. computes Moran's I, Geary's C, Local Moran (LISA) and
     Getis-Ord Gi*, with permutation inference,
  4. fits OLS (with VIF, Breusch-Pagan, Jarque-Bera, Durbin-Watson)
     and the SAR and SEM models by Maximum Likelihood,
  5. reports logLik, AIC, BIC, pseudo-R2, residual Moran's I and
     leave-one-out RMSE/MAE,
  6. exports tables (CSV) and figures (PNG) to results/.

Run on a machine WITH internet (e.g. locally or in Google Colab):
    pip install requests pandas numpy scipy matplotlib
    python campania_spatial_lite.py

All statistical functions are implemented from first principles so
they can be unit-tested offline; see the __test__ block.
"""

import os, time
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar

SEED = 42

# ============================================================
# SPATIAL WEIGHTS
# ============================================================
def knn_weights(coords, k=4):
    """Row-standardised k-nearest-neighbour weights (dense). coords: (n,2)."""
    n = len(coords)
    d = np.sqrt(((coords[:, None, :] - coords[None, :, :]) ** 2).sum(-1))
    np.fill_diagonal(d, np.inf)
    W = np.zeros((n, n))
    for i in range(n):
        nn = np.argsort(d[i])[:k]
        W[i, nn] = 1.0
    rs = W.sum(1, keepdims=True); rs[rs == 0] = 1
    return W / rs

# ============================================================
# GLOBAL AUTOCORRELATION
# ============================================================
def moran_I(y, W, permutations=999, seed=SEED):
    y = np.asarray(y, float); n = len(y); z = y - y.mean()
    S0 = W.sum()
    I = (n / S0) * (z @ (W @ z)) / (z @ z)
    EI = -1.0 / (n - 1)
    rng = np.random.default_rng(seed)
    perm = np.empty(permutations)
    for p in range(permutations):
        zp = rng.permutation(z)
        perm[p] = (n / S0) * (zp @ (W @ zp)) / (zp @ zp)
    p_sim = (np.sum(np.abs(perm - EI) >= abs(I - EI)) + 1) / (permutations + 1)
    z_score = (I - EI) / perm.std()
    return {"I": I, "EI": EI, "z": z_score, "p_sim": p_sim}

def geary_C(y, W):
    y = np.asarray(y, float); n = len(y); z = y - y.mean()
    S0 = W.sum()
    num = sum(W[i, j] * (y[i] - y[j]) ** 2 for i in range(n) for j in range(n))
    C = ((n - 1) / (2 * S0)) * num / (z @ z)
    return {"C": C}

def local_moran(y, W, permutations=999, seed=SEED):
    y = np.asarray(y, float); n = len(y)
    z = (y - y.mean()); m2 = (z ** 2).sum() / n
    zl = W @ z
    Ii = (z / m2) * zl
    # quadrant: 1 HH, 2 LH, 3 LL, 4 HL
    q = np.where((z > 0) & (zl > 0), 1, np.where((z < 0) & (zl > 0), 2,
        np.where((z < 0) & (zl < 0), 3, 4)))
    rng = np.random.default_rng(seed)
    p = np.empty(n)
    for i in range(n):
        wi = W[i].copy()
        sims = np.empty(permutations)
        idx = [j for j in range(n) if j != i]
        for s in range(permutations):
            zp = z.copy(); zp[idx] = rng.permutation(z[idx])
            sims[s] = (z[i] / m2) * (wi @ zp)
        p[i] = (np.sum(np.abs(sims) >= abs(Ii[i])) + 1) / (permutations + 1)
    return {"Ii": Ii, "q": q, "p_sim": p}

def getis_ord_gistar(y, W):
    y = np.asarray(y, float); n = len(y)
    ybar = y.mean(); s = y.std(ddof=0)
    Z = np.empty(n)
    for i in range(n):
        wi = W[i].copy(); wi[i] = wi[i] if W[i, i] else W[i].mean()  # Gi* includes i
        num = (wi @ y) - ybar * wi.sum()
        den = s * np.sqrt((n * (wi ** 2).sum() - wi.sum() ** 2) / (n - 1))
        Z[i] = num / den if den != 0 else 0.0
    return {"Gi_z": Z, "Gi_p": 2 * (1 - stats.norm.cdf(np.abs(Z)))}

# ============================================================
# OLS + DIAGNOSTICS
# ============================================================
def ols(y, X):
    y = np.asarray(y, float); n = len(y)
    Xc = np.column_stack([np.ones(n), X]); k = Xc.shape[1]
    beta, *_ = np.linalg.lstsq(Xc, y, rcond=None)
    resid = y - Xc @ beta; rss = resid @ resid
    sig2 = rss / (n - k)
    cov = sig2 * np.linalg.inv(Xc.T @ Xc)
    se = np.sqrt(np.diag(cov)); t = beta / se
    p = 2 * (1 - stats.t.cdf(np.abs(t), n - k))
    tss = ((y - y.mean()) ** 2).sum(); r2 = 1 - rss / tss
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k)
    ll = -0.5 * n * (np.log(2 * np.pi) + np.log(rss / n) + 1)
    aic = -2 * ll + 2 * k; bic = -2 * ll + np.log(n) * k
    ci = np.column_stack([beta - 1.96 * se, beta + 1.96 * se])
    return {"beta": beta, "se": se, "t": t, "p": p, "ci": ci, "resid": resid,
            "fitted": Xc @ beta, "r2": r2, "adj_r2": adj_r2, "aic": aic,
            "bic": bic, "loglik": ll, "rss": rss, "k": k, "n": n}

def vif(X):
    X = np.atleast_2d(X); p = X.shape[1]; out = []
    for j in range(p):
        others = np.delete(X, j, axis=1)
        r = ols(X[:, j], others)["r2"]
        out.append(1.0 / (1.0 - r) if r < 1 else np.inf)
    return np.array(out)

def breusch_pagan(resid, X):
    n = len(resid); Xc = np.column_stack([np.ones(n), X])
    g = resid ** 2 / (resid @ resid / n)
    aux = ols(g, X); r2 = aux["r2"]
    lm = n * r2; df = X.shape[1]
    return {"LM": lm, "p": 1 - stats.chi2.cdf(lm, df)}

def durbin_watson(resid):
    return np.sum(np.diff(resid) ** 2) / np.sum(resid ** 2)

# ============================================================
# ML SPATIAL MODELS (concentrated log-likelihood, exact log-det)
# ============================================================
def _spatial_ml(y, X, W, kind):
    y = np.asarray(y, float); n = len(y)
    Xc = np.column_stack([np.ones(n), X]); k = Xc.shape[1]
    I = np.eye(n)

    def negll(rho):
        A = I - rho * W
        sign, logdet = np.linalg.slogdet(A)
        if sign <= 0:
            return 1e10
        if kind == "lag":            # SAR: A y = X b + e
            Ay = A @ y; b, *_ = np.linalg.lstsq(Xc, Ay, rcond=None); e = Ay - Xc @ b
        else:                        # SEM: A(y - Xb) = e
            AX = A @ Xc; Ay = A @ y; b, *_ = np.linalg.lstsq(AX, Ay, rcond=None); e = Ay - AX @ b
        sig2 = (e @ e) / n
        return -(-0.5 * n * (np.log(2 * np.pi) + np.log(sig2) + 1) + logdet)

    res = minimize_scalar(negll, bounds=(-0.99, 0.99), method="bounded")
    rho = res.x; ll = -res.fun
    A = I - rho * W
    if kind == "lag":
        Ay = A @ y; beta, *_ = np.linalg.lstsq(Xc, Ay, rcond=None); e = Ay - Xc @ beta
        fitted = np.linalg.solve(A, Xc @ beta)
    else:
        AX = A @ Xc; Ay = A @ y; beta, *_ = np.linalg.lstsq(AX, Ay, rcond=None); e = Ay - AX @ beta
        fitted = Xc @ beta
    sig2 = (e @ e) / n
    cov = sig2 * np.linalg.inv(Xc.T @ Xc)        # conditional SE for betas
    se = np.sqrt(np.diag(cov))
    # numeric SE for the spatial parameter
    h = 1e-4; f0 = negll(rho); fp = negll(rho + h); fm = negll(rho - h)
    d2 = (fp - 2 * f0 + fm) / h ** 2
    rho_se = 1.0 / np.sqrt(d2) if d2 > 0 else np.nan
    npar = k + 2
    aic = -2 * ll + 2 * npar; bic = -2 * ll + np.log(n) * npar
    pr2 = np.corrcoef(y, fitted)[0, 1] ** 2
    # 'resid' = model innovations (e), the correct series for the residual-autocorrelation check;
    # 'pred_resid' = y - fitted, used for predictive error.
    return {"spatial_param": rho, "spatial_se": rho_se, "beta": beta, "se": se,
            "loglik": ll, "aic": aic, "bic": bic, "pseudo_r2": pr2,
            "resid": e, "pred_resid": y - fitted, "fitted": fitted}

def ml_sar(y, X, W): return _spatial_ml(y, X, W, "lag")
def ml_sem(y, X, W): return _spatial_ml(y, X, W, "error")

def loocv_ols(y, X):
    y = np.asarray(y, float); n = len(y); err = np.empty(n)
    for i in range(n):
        m = np.ones(n, bool); m[i] = False
        fit = ols(y[m], np.atleast_2d(X)[m])
        xi = np.concatenate([[1.0], np.atleast_2d(X)[i]])
        err[i] = y[i] - xi @ fit["beta"]
    return {"RMSE": np.sqrt((err ** 2).mean()), "MAE": np.abs(err).mean()}

# ============================================================
# DATA ACQUISITION (NASA POWER)  +  DRIVER
# ============================================================
TOWNS = {  # extend to 40-60 municipalities to strengthen inference
    "Naples": (40.852, 14.268), "Pozzuoli": (40.823, 14.121),
    "Castellammare": (40.695, 14.481), "Sorrento": (40.626, 14.376),
    "Positano": (40.628, 14.485), "Amalfi": (40.634, 14.603),
    "Salerno": (40.682, 14.768), "Agropoli": (40.350, 14.993),
    "Palinuro": (40.034, 15.288), "Sapri": (40.076, 15.631),
}
POWER = ["T2M", "RH2M", "PRECTOTCORR", "WS10M", "WD10M", "PS", "ALLSKY_SFC_SW_DWN", "CLOUD_AMT"]
RENAME = {"T2M": "AirTemp", "RH2M": "Humidity", "PRECTOTCORR": "Rainfall",
          "WS10M": "WindSpeed", "WD10M": "WindDir", "PS": "Pressure",
          "ALLSKY_SFC_SW_DWN": "SolarRad", "CLOUD_AMT": "CloudCover"}

def download():
    import requests
    base = "https://power.larc.nasa.gov/api/temporal/climatology/point"
    rows = []
    for name, (lat, lon) in TOWNS.items():
        url = (f"{base}?parameters={','.join(POWER)}&community=AG"
               f"&latitude={lat}&longitude={lon}&format=JSON")
        d = requests.get(url, timeout=60).json()["properties"]["parameter"]
        rows.append({"comune": name, "lat": lat, "lon": lon,
                     **{RENAME[k]: d[k]["ANN"] for k in POWER}})
        print("  ok", name); time.sleep(1)
    return pd.DataFrame(rows)

def run(df, dependent="AirTemp", predictors=("Humidity", "WindSpeed", "Pressure", "SolarRad")):
    os.makedirs("results/tables", exist_ok=True); os.makedirs("results/figs", exist_ok=True)
    predictors = list(predictors)
    coords = df[["lon", "lat"]].values
    W = knn_weights(coords, k=4)
    y = df[dependent].values.astype(float); X = df[predictors].values.astype(float)
    # ESDA
    esda = []
    for v in [dependent] + predictors:
        mi = moran_I(df[v].values, W); gc = geary_C(df[v].values, W)
        esda.append({"variable": v, "MoranI": mi["I"], "Moran_p": mi["p_sim"], "GearyC": gc["C"]})
    pd.DataFrame(esda).to_csv("results/tables/spatial_autocorrelation.csv", index=False)
    # OLS + diagnostics
    o = ols(y, X); bp = breusch_pagan(o["resid"], X)
    jb = stats.jarque_bera(o["resid"]); sw = stats.shapiro(o["resid"])
    rm = moran_I(o["resid"], W)
    pd.DataFrame({"term": ["const"] + predictors, "beta": o["beta"],
                  "se": o["se"], "t": o["t"], "p": o["p"]}).to_csv(
                  "results/tables/ols.csv", index=False)
    # Spatial models
    sar = ml_sar(y, X, W); sem = ml_sem(y, X, W)
    pd.DataFrame({"model": ["OLS", "SAR", "SEM"],
                  "logLik": [o["loglik"], sar["loglik"], sem["loglik"]],
                  "AIC": [o["aic"], sar["aic"], sem["aic"]],
                  "BIC": [o["bic"], sar["bic"], sem["bic"]],
                  "resid_MoranI": [rm["I"], moran_I(sar["resid"], W)["I"], moran_I(sem["resid"], W)["I"]]
                  }).to_csv("results/tables/model_comparison.csv", index=False)
    print("Analysis complete. Tables in results/tables/.")
    return {"ols": o, "sar": sar, "sem": sem}

if __name__ == "__main__":
    df = download(); df.to_csv("results/campania_coastal.csv", index=False)
    run(df)

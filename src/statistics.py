from __future__ import annotations

import numpy as np
from scipy import stats


def bootstrap_ci(values, statistic=np.mean, n_boot=3000, seed=42, alpha=.05):
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0: return [None, None]
    rng = np.random.default_rng(seed)
    samples = rng.choice(arr, size=(n_boot, len(arr)), replace=True)
    estimates = np.apply_along_axis(statistic, 1, samples)
    return [float(np.quantile(estimates, alpha/2)), float(np.quantile(estimates, 1-alpha/2))]


def bootstrap_corr_ci(x, y, n_boot=2000, seed=42):
    x=np.asarray(x,float); y=np.asarray(y,float); mask=np.isfinite(x)&np.isfinite(y); x=x[mask]; y=y[mask]
    if len(x)<5: return [None,None]
    rng=np.random.default_rng(seed); vals=[]
    for _ in range(n_boot):
        idx=rng.integers(0,len(x),len(x)); rho=stats.spearmanr(x[idx],y[idx]).statistic
        if np.isfinite(rho): vals.append(rho)
    return [float(np.quantile(vals,.025)),float(np.quantile(vals,.975))]


def wilson_interval(k, n, alpha=.05):
    if n == 0: return [None, None]
    z=stats.norm.ppf(1-alpha/2); p=k/n; den=1+z*z/n
    center=(p+z*z/(2*n))/den; half=z*np.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [float(center-half),float(center+half)]


def cliffs_delta_from_u(u, n1, n2):
    return float(2*u/(n1*n2)-1) if n1 and n2 else None


def bh_adjust(pvalues):
    p=np.asarray(pvalues,float); order=np.argsort(p); ranked=p[order]; adjusted=np.empty_like(ranked)
    running=1.0
    for i in range(len(ranked)-1,-1,-1):
        running=min(running,ranked[i]*len(ranked)/(i+1)); adjusted[i]=running
    out=np.empty_like(adjusted); out[order]=np.clip(adjusted,0,1); return out.tolist()


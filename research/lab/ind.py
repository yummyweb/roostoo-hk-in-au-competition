"""Causal indicators on (T,N) arrays. The value at row t uses rows <= t only. Warm-up rows are NaN."""
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def _pad(x, n, like):
    out = np.full(like.shape, np.nan); out[n - 1:] = x; return out


def sma(x, n):
    """Rolling mean. A window that contains a NaN (e.g. another indicator's warm-up) is NaN; later rows recover."""
    bad = np.isnan(x); z = np.zeros((1, x.shape[1]))
    c = np.cumsum(np.vstack([z, np.where(bad, 0., x)]), axis=0); k = np.cumsum(np.vstack([z, bad]), axis=0)
    out = (c[n:] - c[:-n]) / n; out[(k[n:] - k[:-n]) > 0] = np.nan; return _pad(out, n, x)


def ema(x, n):
    """EMA with multiplier 2/(n+1), seeded with the SMA of the first n rows (rows before that are NaN)."""
    out = np.full(x.shape, np.nan); k = 2 / (n + 1)
    first = np.argmax(np.isfinite(x), axis=0)                      # per column: first finite row (skips a NaN warm-up)
    for s in np.unique(first):
        cols = first == s
        if s + n > len(x): continue
        out[s + n - 1, cols] = x[s:s + n, cols].mean(0)
        for t in range(s + n, len(x)): out[t, cols] = out[t - 1, cols] + k * (x[t, cols] - out[t - 1, cols])
    return out


def wma(x, n):
    w = np.arange(1, n + 1, dtype=float); return _pad((sliding_window_view(x, n, axis=0) * w).sum(-1) / w.sum(), n, x)


def rstd(x, n):
    """Rolling population standard deviation."""
    m = sma(x, n); v = sma(x * x, n) - m * m; return np.sqrt(np.maximum(v, 0))


def zscore(x, n):
    s = rstd(x, n); return (x - sma(x, n)) / np.where(s > 0, s, np.nan)


def rmax(x, n):
    return _pad(sliding_window_view(x, n, axis=0).max(-1), n, x)


def rmin(x, n):
    return _pad(sliding_window_view(x, n, axis=0).min(-1), n, x)


def ret(x, n):
    out = np.full(x.shape, np.nan); out[n:] = x[n:] / x[:-n] - 1; return out


def logret(x, n=1):
    out = np.full(x.shape, np.nan); out[n:] = np.log(x[n:] / x[:-n]); return out


def rsi(c, n=14):
    """Wilder's RSI."""
    d = np.diff(c, axis=0); up = np.maximum(d, 0); dn = np.maximum(-d, 0); out = np.full(c.shape, np.nan)
    au = up[:n].mean(0); ad = dn[:n].mean(0); out[n] = np.where(ad > 0, 100 - 100 / (1 + au / np.where(ad > 0, ad, 1)), 100.)
    for t in range(n, len(d)):
        au = (au * (n - 1) + up[t]) / n; ad = (ad * (n - 1) + dn[t]) / n
        out[t + 1] = np.where(ad > 0, 100 - 100 / (1 + au / np.where(ad > 0, ad, 1)), 100.)
    return out


def atr(h, l, c, n=14):
    """Simple moving average of the true range."""
    prev = np.vstack([c[:1], c[:-1]]); tr = np.maximum(h - l, np.maximum(np.abs(h - prev), np.abs(l - prev))); return sma(tr, n)


def bollinger(c, n=20, k=2.):
    mid = sma(c, n); s = rstd(c, n); return mid, mid + k * s, mid - k * s


def efficiency_ratio(c, n):
    """Kaufman efficiency: |net move| / sum of |bar moves| over n bars. Near 1 = clean trend, near 0 = chop."""
    d = np.abs(np.diff(c, axis=0, prepend=c[:1])); path = sma(d, n) * n
    net = np.full(c.shape, np.nan); net[n:] = np.abs(c[n:] - c[:-n]); return net / np.where(path > 0, path, np.nan)


def cross_count(fast, slow, n):
    """Number of times `fast` crossed `slow` in the trailing n bars (the whipsaw count)."""
    sign = np.sign(fast - slow); flip = np.zeros(fast.shape); flip[1:] = (sign[1:] * sign[:-1] < 0)
    flip[np.isnan(sign)] = np.nan; flip[1:][np.isnan(sign[:-1])] = np.nan
    return sma(flip, n) * n


def realized_vol(c, n):
    """Rolling standard deviation of one-bar log returns."""
    return rstd(np.nan_to_num(logret(c, 1)), n)

def seasonal_naive_annual(T, s, L=None):
    return s[T - 1]

def mean_last_3(T, s, L=None):
    return float(np.mean([s[T - i] for i in (1, 2, 3)]))

def metric(calls, labs):
    tp = sum(1 for a, b in zip(calls, labs) if a and b)
    nh, nf = sum(1 for a in calls if a), sum(1 for b in labs if b)
    return dict(precision=tp / nh if nh else 0., recall=tp / nf if nf else 0.,
                f1=2 * tp / (nh + nf) if nh + nf else 0.,
                agreement=sum(bool(a) == bool(b) for a, b in zip(calls, labs)) / len(labs) if labs else 0.,
                tp=tp, fp=nh - tp, fn=nf - tp, n_high=nh, n_flagged=nf)

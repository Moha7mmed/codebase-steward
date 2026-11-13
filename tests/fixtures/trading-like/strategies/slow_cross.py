"""Slow cross strategy."""


def load_prices(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            day, close = line.strip().split(",")
            rows.append((day, float(close)))
    return rows


def moving_average(values, n):
    out = []
    for i in range(len(values)):
        if i + 1 < n:
            out.append(None)
        else:
            window = values[i + 1 - n:i + 1]
            out.append(sum(window) / n)
    return out


def signals(path):
    prices = load_prices(path)
    closes = [c for _, c in prices]
    fast = moving_average(closes, 4)
    slow = moving_average(closes, 7)
    out = []
    for (day, _), f, s in zip(prices, fast, slow):
        if f is None or s is None:
            continue
        out.append((day, "buy" if f > s else "sell"))
    return out

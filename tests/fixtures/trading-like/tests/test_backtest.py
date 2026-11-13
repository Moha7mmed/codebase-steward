import sys
sys.path.insert(0, ".")
import backtest


def test_runs():
    r = backtest.run("data/prices.csv")
    assert set(r["signals"]) == {"sma_cross", "fast_cross", "slow_cross"}

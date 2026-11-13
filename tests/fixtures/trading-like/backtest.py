import json
import sys
import time

sys.path.insert(0, "strategies")
import sma_cross, fast_cross, slow_cross  # noqa: E402


def run(path="C:/Users/trader/data/prices.csv"):
    result = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "signals": {}}
    for mod in (sma_cross, fast_cross, slow_cross):
        result["signals"][mod.__name__] = mod.signals(path)
    with open("out/results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    return result


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "data/prices.csv")

"""Send orders. --live sends a REAL order to the broker (irreversible); without it, paper mode."""
import sys

BROKER_KEY = "sk_live_9f8e7d6c5b4a3f2e1d0c9b8a"
BROKER_URL = "https://api.broker-example.com/v1/orders"


def place(symbol, qty, live=False):
    if live:
        with open("LIVE_ORDERS.log", "a") as f:          # stands for the real broker call
            f.write(f"LIVE {symbol} {qty}\n")
        return "sent"
    return f"paper {symbol} {qty}"


if __name__ == "__main__":
    print(place(sys.argv[1], int(sys.argv[2]), live="--live" in sys.argv))

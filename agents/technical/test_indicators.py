import pandas as pd
import pandas_ta as ta

def test_indicators():
    df = pd.DataFrame({
        "close": [10, 11, 12, 11, 10, 9, 8, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    })
    df.ta.rsi(append=True)
    assert "RSI_14" in df.columns
    print("Indicator test passed!")

if __name__ == "__main__":
    test_indicators()

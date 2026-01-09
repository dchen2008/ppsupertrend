"""
Test script to verify CSV format with all new columns
"""

import csv
import os
from datetime import datetime
from src.trading_bot_enhanced import CSVLogger

def test_csv_columns():
    """Test that CSV logger creates file with correct columns"""

    test_filename = "test_output.csv"

    # Clean up any existing test file
    if os.path.exists(test_filename):
        os.remove(test_filename)

    # Create CSV logger
    logger = CSVLogger(test_filename)

    print("=" * 80)
    print("CSV FORMAT TEST")
    print("=" * 80)

    # Expected columns
    expected_columns = [
        'tradeID', 'name', 'orderTime', 'closeTime', 'duration', 'superTrend', 'pivotPoint',
        'signal', 'type', 'positionSize', 'enterPrice', 'stopLoss', 'closePrice',
        'highestPrice', 'lowestPrice', 'highestProfit', 'lowestLoss',
        'stopLossHit', 'riskRewardRatio', 'profit', 'accountBalance'
    ]

    print(f"\nExpected columns ({len(expected_columns)}):")
    for i, col in enumerate(expected_columns, 1):
        print(f"  {i}. {col}")

    print(f"\nActual columns ({len(logger.fieldnames)}):")
    for i, col in enumerate(logger.fieldnames, 1):
        print(f"  {i}. {col}")

    # Verify columns match
    if logger.fieldnames == expected_columns:
        print("\n✅ Column names match expected structure")
    else:
        print("\n❌ Column mismatch!")
        missing = set(expected_columns) - set(logger.fieldnames)
        extra = set(logger.fieldnames) - set(expected_columns)
        if missing:
            print(f"  Missing: {missing}")
        if extra:
            print(f"  Extra: {extra}")
        return False

    # Test OPEN trade entry
    print("\n" + "-" * 80)
    print("TEST 1: OPEN LONG Position")
    print("-" * 80)

    open_trade_data = {
        'tradeID': 1,
        'name': 'EUR_USD',
        'orderTime': '2026-01-06 10:00:00',
        'closeTime': 'N/A',
        'duration': 'N/A',
        'superTrend': '1.17250',
        'pivotPoint': '1.17200',
        'signal': 'LONG',
        'type': 'buy',
        'positionSize': 10000,
        'enterPrice': '1.17350',
        'stopLoss': '1.17262',
        'closePrice': 'N/A',
        'highestPrice': 'N/A',
        'lowestPrice': 'N/A',
        'highestProfit': 'N/A',
        'lowestLoss': 'N/A',
        'stopLossHit': 'N/A',
        'riskRewardRatio': 'N/A',
        'profit': '0.00',
        'accountBalance': 500000.00
    }

    logger.log_trade(open_trade_data)
    print("✅ OPEN LONG trade logged")
    for key, value in open_trade_data.items():
        print(f"  {key}: {value}")

    # Test CLOSE trade entry
    print("\n" + "-" * 80)
    print("TEST 2: CLOSE Position (Profit)")
    print("-" * 80)

    close_trade_data = {
        'tradeID': 1,
        'name': 'EUR_USD',
        'orderTime': '2026-01-06 10:00:00',
        'closeTime': '2026-01-06 10:45:00',
        'duration': '45m',
        'superTrend': '1.17250',
        'pivotPoint': '1.17200',
        'signal': 'LONG',
        'type': 'CLOSE',
        'positionSize': 10000,
        'enterPrice': '1.17350',
        'stopLoss': '1.17262',
        'closePrice': '1.17420',
        'highestPrice': '1.17480',
        'lowestPrice': '1.17300',
        'highestProfit': '130.00',
        'lowestLoss': '-50.00',
        'stopLossHit': 'FALSE',
        'riskRewardRatio': '0.80',
        'profit': '70.00',
        'accountBalance': 500070.00
    }

    logger.log_trade(close_trade_data)
    print("✅ CLOSE trade logged (with profit)")
    for key, value in close_trade_data.items():
        print(f"  {key}: {value}")

    # Test OPEN SHORT position
    print("\n" + "-" * 80)
    print("TEST 3: OPEN SHORT Position")
    print("-" * 80)

    open_short_data = {
        'tradeID': 2,
        'name': 'EUR_USD',
        'orderTime': '2026-01-06 11:00:00',
        'closeTime': 'N/A',
        'duration': 'N/A',
        'superTrend': '1.17450',
        'pivotPoint': '1.17400',
        'signal': 'SHORT',
        'type': 'sell',
        'positionSize': 10000,
        'enterPrice': '1.17420',
        'stopLoss': '1.17508',
        'closePrice': 'N/A',
        'highestPrice': 'N/A',
        'lowestPrice': 'N/A',
        'highestProfit': 'N/A',
        'lowestLoss': 'N/A',
        'stopLossHit': 'N/A',
        'riskRewardRatio': 'N/A',
        'profit': '0.00',
        'accountBalance': 500070.00
    }

    logger.log_trade(open_short_data)
    print("✅ OPEN SHORT trade logged")
    for key, value in open_short_data.items():
        print(f"  {key}: {value}")

    # Test CLOSE with stop loss hit
    print("\n" + "-" * 80)
    print("TEST 4: CLOSE Position (Stop Loss Hit - Loss)")
    print("-" * 80)

    close_sl_data = {
        'tradeID': 2,
        'name': 'EUR_USD',
        'orderTime': '2026-01-06 11:00:00',
        'closeTime': '2026-01-06 11:30:00',
        'duration': '30m',
        'superTrend': '1.17450',
        'pivotPoint': '1.17400',
        'signal': 'SHORT',
        'type': 'CLOSE',
        'positionSize': 10000,
        'enterPrice': '1.17420',
        'stopLoss': '1.17508',
        'closePrice': '1.17508',
        'highestPrice': '1.17520',
        'lowestPrice': '1.17380',
        'highestProfit': '40.00',
        'lowestLoss': '-100.00',
        'stopLossHit': 'TRUE',
        'riskRewardRatio': '-1.00',
        'profit': '-88.00',
        'accountBalance': 499982.00
    }

    logger.log_trade(close_sl_data)
    print("✅ CLOSE trade logged (stop loss hit)")
    for key, value in close_sl_data.items():
        print(f"  {key}: {value}")

    # Verify CSV file
    print("\n" + "=" * 80)
    print("VERIFYING CSV FILE")
    print("=" * 80)

    with open(test_filename, 'r') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        print(f"\nTotal rows: {len(rows)} (expected: 4)")

        if len(rows) == 4:
            print("✅ Correct number of rows")
        else:
            print("❌ Wrong number of rows")
            return False

        print("\nRow details:")
        for i, row in enumerate(rows, 1):
            print(f"\n  Row {i}:")
            print(f"    tradeID: {row['tradeID']}")
            print(f"    signal: {row['signal']}")
            print(f"    type: {row['type']}")
            print(f"    enterPrice: {row['enterPrice']}")
            print(f"    closePrice: {row['closePrice']}")
            print(f"    profit: {row['profit']}")
            print(f"    duration: {row['duration']}")
            print(f"    highestPrice: {row['highestPrice']}")
            print(f"    lowestPrice: {row['lowestPrice']}")
            print(f"    stopLossHit: {row['stopLossHit']}")

            # Verify all columns are present
            for col in expected_columns:
                if col not in row:
                    print(f"    ❌ Missing column: {col}")
                    return False

    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED!")
    print("=" * 80)
    print(f"\nTest CSV file created: {test_filename}")
    print("You can review it to verify the format.")

    return True

if __name__ == "__main__":
    success = test_csv_columns()
    exit(0 if success else 1)

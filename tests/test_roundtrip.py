import os
import sys
import csv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.gpp_writer import write_gpp_file
from src.gpp_reader import gpp_to_csv


def read_csv_as_rows(path):
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def compare_csv_files(csv1, csv2) -> bool:
    rows1 = read_csv_as_rows(csv1)
    rows2 = read_csv_as_rows(csv2)
    return rows1 == rows2


def main():
    if len(sys.argv) != 2:
        print("Usage: python test_roundtrip.py input.csv")
        sys.exit(1)

    input_csv = sys.argv[1]

    if not os.path.exists(input_csv):
        print(f"Input CSV file not found: {input_csv}")
        sys.exit(1)

    base, _ = os.path.splitext(input_csv)
    gpp_path = base + ".gppcol"
    output_csv = base + ".roundtrip.csv"

    print(f"[1] Writing GPP file: {gpp_path}")
    write_gpp_file(input_csv, gpp_path)

    print(f"[2] Converting back to CSV: {output_csv}")
    gpp_to_csv(gpp_path, output_csv)

    print("[3] Comparing original and round-trip CSV...")
    same = compare_csv_files(input_csv, output_csv)

    if same:
        print("✅ Round-trip successful: files match exactly.")
        sys.exit(0)
    else:
        print("❌ Round-trip FAILED: files differ.")
        sys.exit(1)


if __name__ == "__main__":
    main()

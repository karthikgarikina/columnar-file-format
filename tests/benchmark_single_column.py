import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.gpp_writer import write_gpp_file
from src.gpp_reader import read_gpp_file
import csv
import time
import random



def generate_csv(path: str, rows: int = 200_000):
    print(f"Generating CSV with {rows} rows at {path}...")
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "score", "is_pass"])

        for i in range(rows):
            name = f"user_{i}"
            score = random.uniform(0, 100)
            is_pass = "true" if score >= 40 else "false"
            writer.writerow([i, name, score, is_pass])


def time_read_csv_single_column(path: str, column_name: str) -> float:
    start = time.perf_counter()
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx = header.index(column_name)

        values = []
        for row in reader:
            values.append(row[idx])

    elapsed = time.perf_counter() - start
    print(f"CSV read column '{column_name}': {len(values)} values, took {elapsed:.4f} s")
    return elapsed


def time_read_gpp_single_column(path: str, column_name: str) -> float:
    start = time.perf_counter()
    cols, data, n = read_gpp_file(path, columns=[column_name])
    elapsed = time.perf_counter() - start

    print(f"GPP read column '{column_name}': {n} values, took {elapsed:.4f} s")
    return elapsed


def main():
    csv_path = "data/bench_data.csv"
    gpp_path = "data/bench_data.gppcol"

    if not os.path.exists(csv_path):
        generate_csv(csv_path, rows=200_000)

    if not os.path.exists(gpp_path):
        print("Converting CSV → GPP for benchmark...")
        write_gpp_file(csv_path, gpp_path)

    print("\n--- Benchmark: single column read ---")
    csv_time = time_read_csv_single_column(csv_path, "score")
    gpp_time = time_read_gpp_single_column(gpp_path, "score")

    print("\nResult:")
    print(f"  CSV: {csv_time:.4f} s")
    print(f"  GPP: {gpp_time:.4f} s")


if __name__ == "__main__":
    main()

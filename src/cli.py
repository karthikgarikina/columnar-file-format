#!/usr/bin/env python3

import os
import sys
import csv
import time
import random

from .gpp_writer import write_gpp_file
from .gpp_reader import gpp_to_csv, read_gpp_file, read_header


# ------------ Utility functions ------------

def clear_screen():
    # Simple clear for Windows / Unix
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to continue...")


def print_banner():
    print("=" * 40)
    print("   GPP Columnar File Format CLI")
    print("=" * 40)


# ------------ Helper for CSV comparison (round-trip) ------------

def read_csv_rows(path):
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


def compare_csv_files(path1, path2) -> bool:
    rows1 = read_csv_rows(path1)
    rows2 = read_csv_rows(path2)
    return rows1 == rows2


# ------------ Menu actions ------------

def action_csv_to_gpp():
    print("\n[CSV -> GPP (.gppcol)]")
    input_csv = input("Enter input CSV path: ").strip()
    output_gpp = input("Enter output .gppcol path: ").strip()

    if not os.path.exists(input_csv):
        print(f"❌ Input CSV file not found: {input_csv}")
        return

    try:
        write_gpp_file(input_csv, output_gpp)
        print("✅ Conversion completed.")
    except Exception as e:
        print(f"❌ Error during conversion: {e}")


def action_gpp_to_csv():
    print("\n[GPP (.gppcol) -> CSV]")
    input_gpp = input("Enter input .gppcol path: ").strip()
    output_csv = input("Enter output CSV path: ").strip()

    if not os.path.exists(input_gpp):
        print(f"❌ Input GPP file not found: {input_gpp}")
        return

    try:
        gpp_to_csv(input_gpp, output_csv)
        print("✅ Conversion completed.")
    except Exception as e:
        print(f"❌ Error during conversion: {e}")


def action_show_schema():
    print("\n[Show Schema / Metadata]")
    path = input("Enter .gppcol file path: ").strip()

    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return

    try:
        with open(path, "rb") as f:
            header = read_header(f)
    except Exception as e:
        print(f"❌ Error reading header: {e}")
        return

    print(f"\nFile: {path}")
    print(f"Rows: {header.row_count}")
    print(f"Columns ({header.column_count}):")
    type_map = {
        1: "int32",
        2: "float64",
        3: "string",
        4: "bool",
    }
    for col in header.columns:
        tname = type_map.get(col.type_id, f"unknown({col.type_id})")
        print(f"  - {col.name} ({tname})")
        # If you want more debug info, uncomment:
        # print(f"      offset={col.data_offset}, compressed={col.compressed_size}, uncompressed={col.uncompressed_size}")


def action_read_columns():
    print("\n[Read Specific Columns]")
    path = input("Enter .gppcol file path: ").strip()

    if not os.path.exists(path):
        print(f"❌ File not found: {path}")
        return

    cols_raw = input("Enter column names (comma-separated): ").strip()
    if not cols_raw:
        print("❌ No columns specified.")
        return

    columns = [c.strip() for c in cols_raw.split(",") if c.strip()]
    if not columns:
        print("❌ No valid columns specified.")
        return

    try:
        col_names, data, row_count = read_gpp_file(path, columns=columns)
    except Exception as e:
        print(f"❌ Error reading columns: {e}")
        return

    print(f"\nRead columns: {', '.join(col_names)}")
    print(f"Total rows: {row_count}")

    # Preview first few rows
    preview_n = min(5, row_count)
    print(f"\nFirst {preview_n} rows:")
    for i in range(preview_n):
        row_vals = [str(data[name][i]) for name in col_names]
        print("  " + ", ".join(row_vals))

    choice = input("\nDo you want to save these columns as CSV? (y/n): ").strip().lower()
    if choice == "y":
        out_path = input("Enter output CSV path: ").strip()
        try:
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(col_names)
                for i in range(row_count):
                    row = []
                    for name in col_names:
                        val = data[name][i]
                        if isinstance(val, bool):
                            row.append("true" if val else "false")
                        else:
                            row.append(val)
                    writer.writerow(row)
            print(f"✅ Saved selected columns to {out_path}")
        except Exception as e:
            print(f"❌ Error saving CSV: {e}")


def action_roundtrip_test():
    print("\n[Round-trip Test: CSV -> GPP -> CSV]")
    input_csv = input("Enter input CSV path: ").strip()
    if not os.path.exists(input_csv):
        print(f"❌ Input CSV file not found: {input_csv}")
        return

    output_gpp = input("Enter temporary/output .gppcol path: ").strip()
    roundtrip_csv = input("Enter round-trip CSV output path: ").strip()

    try:
        print("\n[1] Writing GPP file...")
        write_gpp_file(input_csv, output_gpp)

        print("[2] Converting back to CSV...")
        gpp_to_csv(output_gpp, roundtrip_csv)

        print("[3] Comparing original and round-trip CSV files...")
        same = compare_csv_files(input_csv, roundtrip_csv)

        if same:
            print("✅ Round-trip successful: files match exactly.")
        else:
            print("❌ Round-trip FAILED: files differ.")
    except Exception as e:
        print(f"❌ Error during round-trip test: {e}")


def action_benchmark():
    print("\n[Benchmark: CSV vs GPP Single Column Read]")
    print("This will generate a large dataset (if needed),")
    print("convert to GPP, and compare reading a single column.")
    input("Press Enter to continue...")

    csv_path = "data/bench_data.csv"
    gpp_path = "data/bench_data.gppcol"
    column_to_test = "score"

    # Generate CSV if not exists
    if not os.path.exists(csv_path):
        print(f"\nGenerating CSV file: {csv_path} (this may take a moment)...")
        rows = 200_000
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "name", "score", "is_pass"])
            for i in range(rows):
                name = f"user_{i}"
                score = random.uniform(0, 100)
                is_pass = "true" if score >= 40 else "false"
                writer.writerow([i, name, score, is_pass])
        print(f"✅ Generated {rows} rows.")

    # Convert to GPP if not exists
    if not os.path.exists(gpp_path):
        print("\nConverting CSV -> GPP for benchmark...")
        write_gpp_file(csv_path, gpp_path)

    # Time CSV read (one column)
    def time_read_csv_col(path, col_name):
        start = time.perf_counter()
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            idx = header.index(col_name)
            vals = [row[idx] for row in reader]
        elapsed = time.perf_counter() - start
        print(f"CSV:   read column '{col_name}' ({len(vals)} values) in {elapsed:.4f} s")
        return elapsed

    # Time GPP read (one column)
    def time_read_gpp_col(path, col_name):
        start = time.perf_counter()
        _, data, n = read_gpp_file(path, columns=[col_name])
        elapsed = time.perf_counter() - start
        print(f"GPP:   read column '{col_name}' ({n} values) in {elapsed:.4f} s")
        return elapsed

    print("\nRunning benchmark...\n")
    csv_time = time_read_csv_col(csv_path, column_to_test)
    gpp_time = time_read_gpp_col(gpp_path, column_to_test)

    print("\nResult:")
    print(f"  CSV time : {csv_time:.4f} s")
    print(f"  GPP time : {gpp_time:.4f} s")
    if gpp_time > 0:
        print(f"  Speedup  : {csv_time / gpp_time:.2f}x (lower is faster)")
    else:
        print("  Speedup  : (GPP time too small to measure)")

    print("\nBenchmark complete.")


# ------------ Main loop ------------

def main_menu():
    while True:
        clear_screen()
        print_banner()
        print("1) CSV -> GPP (.gppcol)")
        print("2) GPP (.gppcol) -> CSV")
        print("3) Show file schema")
        print("4) Read specific columns")
        print("5) Round-trip test (CSV -> GPP -> CSV)")
        print("6) Run benchmark (CSV vs GPP)")
        print("0) Exit")
        choice = input("\nEnter your choice: ").strip()

        if choice == "1":
            clear_screen()
            action_csv_to_gpp()
            pause()
        elif choice == "2":
            clear_screen()
            action_gpp_to_csv()
            pause()
        elif choice == "3":
            clear_screen()
            action_show_schema()
            pause()
        elif choice == "4":
            clear_screen()
            action_read_columns()
            pause()
        elif choice == "5":
            clear_screen()
            action_roundtrip_test()
            pause()
        elif choice == "6":
            clear_screen()
            action_benchmark()
            pause()
        elif choice == "0":
            print("\nGoodbye! 👋")
            break
        else:
            print("\n❌ Invalid choice. Please try again.")
            pause()


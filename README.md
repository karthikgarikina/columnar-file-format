# GPP Columnar File Format

A from-scratch implementation of a **columnar analytical file format** (similar to Parquet/ORC) written in Python.

---

## 🚀 Overview

This project:

- Defines a custom **binary columnar file format** (`.gppcol`)
- Includes a **writer** (CSV → GPP) & **reader** (GPP → CSV)
- Supports **column pruning** for fast selective reads
- Uses **zlib compression per column**
- Includes **CLI tools + tests + benchmarks**
- Demonstrates performance improvement for analytical workloads

---

## ✨ Features

- Columnar storage — each column stored independently & compressed
- File header stores:
  - magic number, version, endianness
  - row count, column count
  - per-column metadata: name, type, offset, compressed/uncompressed sizes
- Supported types:
  - `int32`, `float64`, `string` (UTF-8 w/ offsets), `bool`
- Full-file read + **read only selected columns**
- Round-trip CSV → GPP → CSV **bitwise identical**
- Benchmark example: single column read is **faster** than CSV

---

## 📂 Project Structure

```
columnar-file-format/
├─ src/
│ ├─ __init__.py
│ ├─ gpp_writer.py        # CSV -> GPP
│ ├─ gpp_reader.py        # GPP -> CSV/Python reader
│ └─ cli.py               # CLI & interactive menu
├─ data/
│ ├─ test.csv
│ └─ benchmark results generated here
├─ tests/
│ ├─ test_roundtrip.py
│ └─ benchmark_single_column.py
├─ SPEC.md
├─ README.md
└─ main.py                # Entry point (recommended)
```

---

## ⚡ Quick Start

```bash
git clone <repo-url>
cd columnar-file-format
python main.py
```

You will see:

```
========================================
   GPP Columnar File Format CLI
========================================
1) CSV -> GPP (.gppcol)
2) GPP (.gppcol) -> CSV
3) Show file schema
4) Read specific columns
5) Round-trip test
6) Run benchmark
0) Exit
```

---

## 🧪 CLI Usage

### 1) Convert CSV → GPP  
Converts CSV into compressed columnar `.gppcol`.

### 2) Convert GPP → CSV  
Restores CSV from `.gppcol` fully.

### 3) View Schema  
Shows metadata, row count, column names & types.

### 4) Selective Column Read  
Reads only chosen columns (fast due to column pruning).

Example:

```
Enter columns: id,name
```

### 5) Round-Trip Test  
Verifies CSV → GPP → CSV integrity.

Output:

```
✔ Round-trip successful (files match)
```

### 6) Benchmark

```
CSV: 0.42s
GPP: 0.12s
Speedup: ~3.5x
```

---

## 🧪 Running Tests / Using Modules Manually

You can run tests or use writer/reader modules independently for custom workflows.

```bash
# Round-trip integrity test
python tests/test_roundtrip.py data/test.csv
# Benchmark
python tests/benchmark_single_column.py
```

---

## 🔥 Future Enhancements

- 🟡 Null value support
- 🟡 More data types (date, decimal)
- 🟡 Dictionary encoding for repeated strings
- 🟡 Chunked row-groups → predicate pushdown
- 🟡 Optional compression: Snappy/LZ4/ZSTD

---

## 🙌 Final Words

Thank you for checking out this project!  
Clone → Run → Experiment → Learn how real data formats work.

> Note: For easier understanding and demonstrations, the sample dataset included here is intentionally small.  
> However, this system is fully capable of handling large datasets efficiently — as long as the columns follow the supported data types.


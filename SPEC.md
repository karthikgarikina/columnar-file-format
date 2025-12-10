# GPP Columnar File Format Specification (`.gppcol`)

## 1. Overview

The **GPP Columnar Format** is a simple, custom, binary, **columnar** storage format for tabular data.

Key properties:

- Columnar layout: each column stored as a **separate contiguous block**
- Per-column **zlib compression**
- Supports **selective column reads** (column pruning) using header offsets
- Supported data types:
  - 32-bit signed integer (`int32`)
  - 64-bit floating point (`float64`)
  - UTF-8 encoded variable-length string (`string`)
  - Boolean (`bool`)

Default file extension: **`.gppcol`**  
All multi-byte integers and floats are stored in **little-endian** byte order.

---

## 2. High-level File Layout

A `.gppcol` file is laid out as:

+----------------------+
| File Header          |
| - Magic + Version    |
| - Endianness flag    |
| - Row count          |
| - Column count       |
| - Column metadata[]  |
+----------------------+
| Column 0 Block       |
+----------------------+
| Column 1 Block       |
+----------------------+
| ...                  |
+----------------------+
| Column N-1 Block     |
+----------------------+

Each **column block** is a zlib-compressed blob that, once decompressed, contains the column data in a type-specific layout.

The **header** contains enough metadata to:

- know the schema (column names and types),
- know the number of rows,
- locate each column block via **byte offsets**,
- know compressed and uncompressed sizes.

---

## 3. Primitive Types

Supported logical types and their binary representations:

|Type ID | Logical Type | Binary Representation (Uncompressed)                     |
|--------|--------------|----------------------------------------------------------|
| `1`    | `int32`      | 4-byte signed integer, little-endian                     |
| `2`    | `float64`    | 8-byte IEEE 754 floating point, little-endian            |
| `3`    | `string`     | See string column layout (section 5.3)                   |
| `4`    | `bool`       | 1 byte per value: `0x00` = false, `0x01` = true          |

Type IDs are stored as a single **unsigned byte** (`uint8`).

---

## 4. Header Layout

All numeric fields are in **little-endian** format.

### 4.1 Fixed Part

| Offset (bytes) | Size  | Type    | Field           | Description                                      |
|----------------|-------|---------|-----------------|--------------------------------------------------|
| 0              | 4     | bytes   | `magic`         | ASCII `"GPP1"`                                   |
| 4              | 1     | `uint8` | `version`       | Format version. Start with `1`.                  |
| 5              | 1     | `uint8` | `endianness`    | `1` = little-endian (current), `0` reserved      |
| 6              | 2     | bytes   | reserved        | Reserved (set to `0x00 0x00` for now)            |
| 8              | 8     | `uint64`| `row_count`     | Total number of rows in the table                |
| 16             | 4     | `uint32`| `column_count`  | Number of columns                                |

Total fixed header size so far: **20 bytes**.

### 4.2 Per-Column Metadata

Immediately after the fixed header, we store **`column_count` column metadata entries**, one after another.

For each column **i** (from 0 to `column_count - 1`):

| Field                  | Type     | Description                                             |
|------------------------|----------|---------------------------------------------------------|
| `name_len`             | `uint16` | Length of column name in bytes (UTF-8)                  |
| `name_bytes`           | `bytes`  | Column name as UTF-8 bytes                              |
| `type_id`              | `uint8`  | Data type ID (1=int32, 2=float64, 3=string, 4=bool)     |
| `data_offset`          | `uint64` | Absolute byte offset from start of file to column block |
| `compressed_size`      | `uint64` | Size in bytes of the compressed column block            |
| `uncompressed_size`    | `uint64` | Size in bytes after decompression                       |

The column metadata is therefore:

[ name_len (2 bytes) ]
[ name_bytes (name_len bytes) ]
[ type_id (1 byte) ]
[ data_offset (8 bytes) ]
[ compressed_size (8 bytes) ]
[ uncompressed_size (8 bytes) ]

The total header length is: header_size = 20 (fixed) + sum over columns( 2 + name_len[i] + 1 + 8 + 8 + 8 )

The first column block starts at `min(data_offset)` among all columns.

---

## 5. Column Block Layouts (Uncompressed)

Each column block is stored in the file as:

[ zlib_compressed( column_uncompressed_payload ) ]

The header tells you `data_offset`, `compressed_size`, and `uncompressed_size`.

To read a column:

1. `seek` to `data_offset`
2. read `compressed_size` bytes
3. `zlib.decompress(...)`
4. interpret the uncompressed buffer according to the type-specific layout below.

Let `N = row_count` from the header.

### 5.1 `int32` Column (type_id = 1)

Uncompressed layout:

[ value_0 (4 bytes) ][ value_1 (4 bytes) ] ... [ value_{N-1} (4 bytes) ]

- Total size: `N * 4` bytes.
- Each value is a 32-bit signed integer, little-endian.

### 5.2 `float64` Column (type_id = 2)

Uncompressed layout:

[ value_0 (8 bytes) ][ value_1 (8 bytes) ] ... [ value_{N-1} (8 bytes) ]
- Total size: `N * 8` bytes.
- Each value is a 64-bit IEEE 754 float, little-endian.

### 5.3 `string` Column (type_id = 3)

Strings are variable-length, so we split them into:

- an **offsets array** indicating string boundaries
- a **byte blob** containing all concatenated UTF-8 bytes

Uncompressed layout:

[ offsets[0] (uint32) ]
[ offsets[1] (uint32) ]
  ...
[ offsets[N] (uint32) ]
[ data_bytes ...      ]

Where:

- `offsets` has length **N + 1**
- `offsets[0]` = 0
- For each row `i` (0 ≤ i < N), the bytes of string `i` are:

data_bytes[ offsets[i] : offsets[i+1] ]

- `offsets[N]` = total number of bytes in `data_bytes`

Thus:

- Offsets array size: `(N + 1) * 4` bytes
- Data bytes size: `offsets[N]` bytes
- Total uncompressed size: `(N + 1) * 4 + offsets[N]`

All strings are UTF-8 encoded, with **no null-terminator**.

### 5.4 `bool` Column (type_id = 4)

Uncompressed layout:

[ b_0 (1 byte) ][ b_1 (1 byte) ] ... [ b_{N-1} (1 byte) ]

- `b_i = 0x00` → false
- `b_i = 0x01` → true
- Any other value is considered invalid.

Total size: `N` bytes.

---

## 6. Writing Process (Writer Logic Summary)

Given a CSV with `row_count = N` and `column_count = M`:

1. **Parse CSV**
   - Read header row → column names
   - For each column, determine its type (`int32`, `float64`, `string`, `bool`)
2. **Build column uncompressed buffers** according to type:
   - `int32`/`float64`/`bool` → pack values sequentially
   - `string` → build `offsets` + `data_bytes`
3. **Compress each column buffer with zlib**
   - `compressed = zlib.compress(uncompressed)`
   - Note `compressed_size = len(compressed)`
   - Note `uncompressed_size = len(uncompressed)`
4. **Compute offsets**
   - Start with `current_offset = header_size`
   - For each column in order:
     - `data_offset = current_offset`
     - `current_offset += compressed_size`
5. **Write header**
   - Fixed header fields
   - For each column: write metadata with name, type_id, data_offset, sizes
6. **Write column blocks**
   - Write compressed blobs in the same order as metadata.

---

## 7. Reading Process (Reader Logic Summary)

To read the full table:

1. **Read and validate header**
   - Check `magic == "GPP1"`
   - Check `version == 1`
   - Read `row_count`, `column_count`
   - Parse all column metadata into an in-memory schema structure
2. **For each column**
   - Use `data_offset` and `compressed_size`
   - `seek(data_offset)` in file
   - `read(compressed_size)` bytes
   - `zlib.decompress` → uncompressed column buffer
   - Interpret buffer according to `type_id`
3. **Reconstruct rows**
   - Combine column arrays row-by-row if needed
   - Or keep data as a dict of columns: `{"col_name": [values...]}`

To **read only a subset of columns**:

1. Read header and schema
2. Filter columns to the requested set (e.g. only `["name", "age"]`)
3. For each requested column only:
   - Seek to `data_offset`, read and decompress
4. Ignore all other columns (no i/o, no decompression)

This achieves **column pruning** and faster selective reads.

---

## 8. Example

Given CSV:

```csv
id,name,score,is_pass
1,Alice,95.5,true
2,Bob,88.0,true
3,Chris,60.0,false
row_count = 3

column_count = 4

Types:

id → int32

name → string

score → float64

is_pass → bool

The header will contain 4 column metadata entries, each with:

name ("id", "name", "score", "is_pass")

type_id (1, 3, 2, 4)

data_offset, compressed_size, uncompressed_size

name column uncompressed layout:

offsets length = N + 1 = 4

Strings: "Alice", "Bob", "Chris"

UTF-8 data bytes: b"AliceBobChris"

Byte lengths: 5, 3, 5

offsets:

offsets[0] = 0

offsets[1] = 5

offsets[2] = 8

offsets[3] = 13 (total length)

So:
uncompressed_name_buffer =
    [0, 5, 8, 13] as uint32s +
    b"AliceBobChris"
9. Versioning and Future Extensions
version field currently set to 1.

Reserved bytes in header can be used later (e.g. flags, compression type).

Future enhancements (not required for v1):

Row groups / multiple blocks per column

Dictionary encoding for strings

NULL / missing value markers

Additional data types (date, timestamp, etc.)
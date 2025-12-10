import csv
import struct
import zlib
from dataclasses import dataclass
from typing import List, Dict, Any, Tuple


# ---------- SPEC CONSTANTS ----------

MAGIC = b"GPP1"
VERSION = 1
ENDIANNESS_FLAG = 1  # 1 = little-endian

TYPE_INT32 = 1
TYPE_FLOAT64 = 2
TYPE_STRING = 3
TYPE_BOOL = 4


@dataclass
class ColumnMeta:
    name: str
    type_id: int
    data_offset: int
    compressed_size: int
    uncompressed_size: int


# ---------- TYPE INFERENCE ----------

def infer_column_type(values: List[str]) -> int:
    """
    Very simple type inference:
    1) bool if all values are 'true'/'false' (case insensitive)
    2) int32 if all values parse as int
    3) float64 if all values parse as float
    4) else string
    """

    cleaned = [v.strip() for v in values]

    # Try bool
    bool_vals = {"true", "false"}
    if all(v.lower() in bool_vals for v in cleaned):
        return TYPE_BOOL

    # Try int
    try:
        for v in cleaned:
            int(v)
        return TYPE_INT32
    except ValueError:
        pass

    # Try float
    try:
        for v in cleaned:
            float(v)
        return TYPE_FLOAT64
    except ValueError:
        pass

    # Fallback string
    return TYPE_STRING


# ---------- COLUMN BUFFER BUILDERS (UNCOMPRESSED) ----------

def build_int32_buffer(values: List[str]) -> bytes:
    buf = bytearray()
    for v in values:
        iv = int(v.strip())
        buf += struct.pack("<i", iv)  # little-endian int32
    return bytes(buf)


def build_float64_buffer(values: List[str]) -> bytes:
    buf = bytearray()
    for v in values:
        fv = float(v.strip())
        buf += struct.pack("<d", fv)  # little-endian float64
    return bytes(buf)


def build_bool_buffer(values: List[str]) -> bytes:
    buf = bytearray()
    for v in values:
        val = v.strip().lower()
        if val == "true":
            b = 1
        elif val == "false":
            b = 0
        else:
            raise ValueError(f"Invalid bool value: {v}")
        buf += struct.pack("<?", bool(b))  # bool as 1 byte (0/1)
    return bytes(buf)


def build_string_buffer(values: List[str]) -> bytes:
    """
    Layout:
        [offsets (N+1) * uint32] + [concatenated UTF-8 bytes]
    """
    offsets: List[int] = [0]
    data_bytes = bytearray()

    for v in values:
        encoded = v.encode("utf-8")
        data_bytes += encoded
        offsets.append(len(data_bytes))

    # Build offsets array
    buf = bytearray()
    for off in offsets:
        buf += struct.pack("<I", off)  # uint32

    # Append data bytes
    buf += data_bytes
    return bytes(buf)


def build_column_buffer(values: List[str], type_id: int) -> bytes:
    if type_id == TYPE_INT32:
        return build_int32_buffer(values)
    elif type_id == TYPE_FLOAT64:
        return build_float64_buffer(values)
    elif type_id == TYPE_BOOL:
        return build_bool_buffer(values)
    elif type_id == TYPE_STRING:
        return build_string_buffer(values)
    else:
        raise ValueError(f"Unknown type_id: {type_id}")


# ---------- MAIN: CSV → GPP ----------

def read_csv_columns(csv_path: str) -> Tuple[List[str], Dict[str, List[str]]]:
    """
    Reads CSV into column-wise structure.
    Returns: (column_names, {col_name: [values...]})
    Assumptions:
      - First row is header
      - No missing values
    """
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        raise ValueError("Empty CSV")

    header = rows[0]
    data_rows = rows[1:]

    columns: Dict[str, List[str]] = {name: [] for name in header}

    for row in data_rows:
        if len(row) != len(header):
            raise ValueError("Inconsistent row length in CSV")
        for name, value in zip(header, row):
            columns[name].append(value)

    return header, columns


def write_gpp_file(csv_path: str, out_path: str) -> None:
    # 1. Read CSV into columns
    col_names, col_data = read_csv_columns(csv_path)
    row_count = len(next(iter(col_data.values()))) if col_data else 0
    column_count = len(col_names)

    # 2. Infer types and build uncompressed buffers
    column_types: Dict[str, int] = {}
    uncompressed_buffers: Dict[str, bytes] = {}
    compressed_buffers: Dict[str, bytes] = {}
    column_metas: List[ColumnMeta] = []

    # First pass: build buffers and compress (without offsets)
    for name in col_names:
        values = col_data[name]
        type_id = infer_column_type(values)
        column_types[name] = type_id

        uncompressed = build_column_buffer(values, type_id)
        compressed = zlib.compress(uncompressed)

        uncompressed_buffers[name] = uncompressed
        compressed_buffers[name] = compressed

        # Temporarily set offset=0, will compute after header size known
        column_metas.append(
            ColumnMeta(
                name=name,
                type_id=type_id,
                data_offset=0,
                compressed_size=len(compressed),
                uncompressed_size=len(uncompressed),
            )
        )

    # 3. Compute header size
    # Fixed header = 20 bytes
    header_size = 20
    for meta in column_metas:
        # name_len(uint16) + name_bytes + type_id(uint8) + 3x uint64
        name_bytes = meta.name.encode("utf-8")
        name_len = len(name_bytes)
        header_size += 2 + name_len + 1 + 8 + 8 + 8

    # 4. Assign data_offset for each column (sequential after header)
    current_offset = header_size
    for meta in column_metas:
        meta.data_offset = current_offset
        current_offset += meta.compressed_size

    # 5. Build header bytes
    header_buf = bytearray()

    # Fixed part
    header_buf += MAGIC                     # 4 bytes
    header_buf += struct.pack("<B", VERSION)        # 1 byte
    header_buf += struct.pack("<B", ENDIANNESS_FLAG)  # 1 byte
    header_buf += b"\x00\x00"               # reserved 2 bytes
    header_buf += struct.pack("<Q", row_count)      # uint64
    header_buf += struct.pack("<I", column_count)   # uint32

    # Per-column metadata
    for meta in column_metas:
        name_bytes = meta.name.encode("utf-8")
        name_len = len(name_bytes)

        header_buf += struct.pack("<H", name_len)    # uint16
        header_buf += name_bytes                     # name bytes
        header_buf += struct.pack("<B", meta.type_id)          # type_id uint8
        header_buf += struct.pack("<Q", meta.data_offset)      # uint64
        header_buf += struct.pack("<Q", meta.compressed_size)  # uint64
        header_buf += struct.pack("<Q", meta.uncompressed_size)  # uint64

    # 6. Write to file: header + column blocks
    with open(out_path, "wb") as f:
        # header
        f.write(header_buf)

        # columns in same order as metadata / col_names
        for meta in column_metas:
            comp = compressed_buffers[meta.name]
            f.write(comp)

    print(f"Wrote {out_path}")
    print(f"Rows: {row_count}, Columns: {column_count}")
    for meta in column_metas:
        print(f"  - {meta.name}: type={meta.type_id}, "
              f"offset={meta.data_offset}, "
              f"compressed={meta.compressed_size}, "
              f"uncompressed={meta.uncompressed_size}")


if __name__ == "__main__":
    # Simple manual test example:
    # Change these paths as needed or call from another script.
    import sys
    if len(sys.argv) != 3:
        print("Usage: python gpp_writer.py input.csv output.gppcol")
        sys.exit(1)

    write_gpp_file(sys.argv[1], sys.argv[2])

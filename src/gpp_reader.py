import struct
import zlib
import csv
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Any


# ---------- SPEC CONSTANTS (must match writer) ----------

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


@dataclass
class FileHeader:
    row_count: int
    column_count: int
    columns: List[ColumnMeta]


# ---------- HEADER PARSING ----------

def read_fixed_header(f) -> Tuple[int, int]:
    """
    Reads and validates the fixed 20-byte header.
    Returns: (row_count, column_count)
    """
    fixed = f.read(20)
    if len(fixed) != 20:
        raise ValueError("File too small to be a valid GPP file")

    magic = fixed[0:4]
    if magic != MAGIC:
        raise ValueError(f"Invalid magic: {magic}, not a GPP file")

    version = fixed[4]
    if version != VERSION:
        raise ValueError(f"Unsupported version: {version}")

    endianness = fixed[5]
    if endianness != ENDIANNESS_FLAG:
        raise ValueError(f"Unsupported endianness flag: {endianness}")

    # bytes 6-7 reserved
    row_count = struct.unpack("<Q", fixed[8:16])[0]
    column_count = struct.unpack("<I", fixed[16:20])[0]

    return row_count, column_count


def read_column_metadata(f, column_count: int) -> List[ColumnMeta]:
    columns: List[ColumnMeta] = []

    for _ in range(column_count):
        # name_len
        name_len_bytes = f.read(2)
        if len(name_len_bytes) != 2:
            raise ValueError("Unexpected EOF while reading column name length")

        (name_len,) = struct.unpack("<H", name_len_bytes)

        # name_bytes
        name_bytes = f.read(name_len)
        if len(name_bytes) != name_len:
            raise ValueError("Unexpected EOF while reading column name")

        name = name_bytes.decode("utf-8")

        # type_id
        type_id_bytes = f.read(1)
        if len(type_id_bytes) != 1:
            raise ValueError("Unexpected EOF while reading type_id")
        type_id = type_id_bytes[0]

        # offsets and sizes (3x uint64)
        rest = f.read(8 + 8 + 8)
        if len(rest) != 24:
            raise ValueError("Unexpected EOF while reading column metadata sizes")

        data_offset, compressed_size, uncompressed_size = struct.unpack("<QQQ", rest)

        columns.append(
            ColumnMeta(
                name=name,
                type_id=type_id,
                data_offset=data_offset,
                compressed_size=compressed_size,
                uncompressed_size=uncompressed_size,
            )
        )

    return columns


def read_header(f) -> FileHeader:
    row_count, column_count = read_fixed_header(f)
    columns = read_column_metadata(f, column_count)
    return FileHeader(row_count=row_count, column_count=column_count, columns=columns)


# ---------- COLUMN DECODERS (UNCOMPRESSED) ----------

def decode_int32_column(buf: bytes, row_count: int) -> List[int]:
    if len(buf) != row_count * 4:
        raise ValueError("Int32 column size mismatch")
    values = []
    for (val,) in struct.iter_unpack("<i", buf):
        values.append(val)
    return values


def decode_float64_column(buf: bytes, row_count: int) -> List[float]:
    if len(buf) != row_count * 8:
        raise ValueError("Float64 column size mismatch")
    values = []
    for (val,) in struct.iter_unpack("<d", buf):
        values.append(val)
    return values


def decode_bool_column(buf: bytes, row_count: int) -> List[bool]:
    if len(buf) != row_count:
        raise ValueError("Bool column size mismatch")
    return [b == 1 for b in buf]


def decode_string_column(buf: bytes, row_count: int) -> List[str]:
    # offsets length = (N+1) * 4 bytes
    offsets_count = row_count + 1
    offsets_bytes_len = offsets_count * 4

    if len(buf) < offsets_bytes_len:
        raise ValueError("String column buffer too small for offsets")

    offsets_bytes = buf[:offsets_bytes_len]
    data_bytes = buf[offsets_bytes_len:]

    # read offsets
    offsets = list(struct.iter_unpack("<I", offsets_bytes))
    offsets = [o[0] for o in offsets]

    if len(offsets) != offsets_count:
        raise ValueError("String offsets count mismatch")

    if offsets[-1] != len(data_bytes):
        # Not strictly necessary, but a good sanity check
        raise ValueError("String offsets last value != data bytes length")

    result: List[str] = []
    for i in range(row_count):
        start = offsets[i]
        end = offsets[i + 1]
        s = data_bytes[start:end].decode("utf-8")
        result.append(s)

    return result


def decode_column_uncompressed(buf: bytes, type_id: int, row_count: int) -> List[Any]:
    if type_id == TYPE_INT32:
        return decode_int32_column(buf, row_count)
    elif type_id == TYPE_FLOAT64:
        return decode_float64_column(buf, row_count)
    elif type_id == TYPE_BOOL:
        return decode_bool_column(buf, row_count)
    elif type_id == TYPE_STRING:
        return decode_string_column(buf, row_count)
    else:
        raise ValueError(f"Unknown type_id: {type_id}")


# ---------- MAIN READER API ----------

def read_gpp_file(path: str, columns: Optional[List[str]] = None) -> Tuple[List[str], Dict[str, List[Any]], int]:
    """
    Reads a .gppcol file.

    :param path: path to .gppcol file
    :param columns: list of column names to read, or None for all
    :return: (column_names, data_dict, row_count)
             where data_dict[name] = list of python values
    """
    with open(path, "rb") as f:
        header = read_header(f)

        # Build name -> meta mapping
        meta_by_name: Dict[str, ColumnMeta] = {c.name: c for c in header.columns}

        # Determine which columns to read
        if columns is None:
            read_names = [c.name for c in header.columns]
        else:
            # preserve requested order, validate names
            read_names = []
            for name in columns:
                if name not in meta_by_name:
                    raise KeyError(f"Requested column not found: {name}")
                read_names.append(name)

        result_data: Dict[str, List[Any]] = {}

        for name in read_names:
            meta = meta_by_name[name]

            # Seek and read compressed block only for this column
            f.seek(meta.data_offset)
            comp = f.read(meta.compressed_size)
            if len(comp) != meta.compressed_size:
                raise ValueError(f"Unexpected EOF while reading column {name}")

            # Decompress
            uncompressed = zlib.decompress(comp)

            if len(uncompressed) != meta.uncompressed_size:
                raise ValueError(f"Uncompressed size mismatch for column {name}")

            # Decode according to type
            values = decode_column_uncompressed(uncompressed, meta.type_id, header.row_count)
            result_data[name] = values

    return read_names, result_data, header.row_count


# ---------- CLI: GPP → CSV (custom_to_csv) ----------

def gpp_to_csv(gpp_path: str, csv_path: str) -> None:
    col_names, data, row_count = read_gpp_file(gpp_path, columns=None)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # header
        writer.writerow(col_names)

        # rows
        for i in range(row_count):
            row = []
            for name in col_names:
                val = data[name][i]
                # Convert bool to "true"/"false" for symmetry with writer
                if isinstance(val, bool):
                    row.append("true" if val else "false")
                else:
                    row.append(val)
            writer.writerow(row)

    print(f"Wrote CSV: {csv_path}")
    print(f"Rows: {row_count}, Columns: {len(col_names)}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: python gpp_reader.py input.gppcol output.csv")
        sys.exit(1)

    gpp_to_csv(sys.argv[1], sys.argv[2])

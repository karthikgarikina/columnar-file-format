from src.gpp_reader import read_gpp_file

cols, data, n = read_gpp_file("test.gppcol", columns=["name", "score"])
print("Columns:", cols)
print("Rows:", n)
print("Names:", data["name"])
print("Scores:", data["score"])

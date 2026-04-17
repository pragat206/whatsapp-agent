from app.utils.csv_parser import parse, suggest_mapping, iter_rows


def test_parse_and_suggest():
    csv = b"Name,Phone,City\nRajesh,+919876543210,Mumbai\nPriya,9876501234,Pune\n"
    df = parse(csv, "upload.csv")
    assert list(df.columns) == ["Name", "Phone", "City"]
    rows = iter_rows(df)
    assert rows[0]["Phone"] == "+919876543210"

    suggestion = suggest_mapping(list(df.columns))
    assert suggestion["Name"] == "name"
    assert suggestion["Phone"] == "phone"
    assert suggestion["City"] == "city"

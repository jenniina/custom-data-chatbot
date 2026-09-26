"""Command-line document converter, with no API calls."""
import argparse
from pathlib import Path

from context_me.documents import convert_docx, dump_document


def main():
    parser = argparse.ArgumentParser(description="Convert a Word .docx file to Context Me JSON.")
    parser.add_argument("input", type=Path)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file")
    args = parser.parse_args()
    output = args.output or args.input.with_suffix(".json")
    try:
        if output.resolve() == args.input.resolve():
            raise ValueError("Output must differ from the original document.")
        document = convert_docx(args.input.read_bytes(), args.input.name)
        with output.open("w" if args.force else "x", encoding="utf-8") as handle:
            handle.write(dump_document(document))
    except Exception as error:
        parser.exit(1, f"Conversion failed: {error}\n")
    print(f"Saved {len(document['chunks'])} passages to {output}")


if __name__ == "__main__":
    main()

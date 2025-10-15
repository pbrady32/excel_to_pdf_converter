"""Utility script to regenerate the sample worksheet PDF."""

from __future__ import annotations

from pathlib import Path
import yaml

from app.pdf_build import build_pdf


def main() -> None:
    layout = yaml.safe_load(Path("config/layout.yaml").read_text(encoding="utf-8"))
    options = yaml.safe_load(Path("config/options.yaml").read_text(encoding="utf-8"))
    layout["tax_year"] = "2024"

    items = [
        "Please upload your W2 from SYNAPSES IOM LLC.",
        "Please upload your W2 from Stakey Labatories Inc..",
        "Please upload your 1099-INT from Raymond James 4269.",
        "Please upload your 1099-INT from Raymond James-3233.",
        "Please provide your 1099-DIV from Raymond James 6115.",
        "Please upload your 1099-MISC from American Hearing Benefit.",
        "Please upload your W2 from SYNAPSES IOM LLC.",
        "Please upload your W2 from Stakey Labatories Inc..",
        "Please upload your 1099-INT from Raymond James 4269.",
        "Please upload your 1099-INT from Raymond James-3233.",
        "Please provide your 1099-DIV from Raymond James 6115.",
        "Please upload your 1099-MISC from American Hearing Benefit.",
    ]

    pdf_bytes, page_count = build_pdf("Michael H McKay", items, layout, options)
    output_path = Path("sample.pdf")
    output_path.write_bytes(pdf_bytes)
    print(f"Wrote {output_path} ({page_count} page{'s' if page_count != 1 else ''})")


if __name__ == "__main__":  # pragma: no cover
    main()

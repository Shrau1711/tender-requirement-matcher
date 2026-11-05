"""Reading pictures of pages (OCR): the model (model.py, the default) or EasyOCR on this computer (local.py), chosen in
readers.py by the OCR and OCR_LANGS settings. compare.py judges one reading against another."""
from app.reading.ocr.model import (
    MIN_ROW_CELLS,
    OCR_DPI,
    PROMPT,
    ImageReader,
    Transcriber,
    is_table_row,
    render_page,
)
from app.reading.ocr.readers import OCR, OCR_LANGS, reader_for, reader_setting

__all__ = ["MIN_ROW_CELLS", "OCR", "OCR_DPI", "OCR_LANGS", "PROMPT", "ImageReader", "Transcriber", "is_table_row",
           "reader_for", "reader_setting", "render_page"]

"""Windows-only QA fallback when bundled LibreOffice is unavailable."""
from pathlib import Path
import win32com.client

folder = Path(__file__).resolve().parents[1] / "tmp" / "bth-assistant-qa"
app = win32com.client.DispatchEx("Word.Application")
document = None
try:
    app.Visible = False
    app.DisplayAlerts = 0
    document = app.Documents.Open(str(folder / "sample.docx"), ReadOnly=True, AddToRecentFiles=False)
    document.ExportAsFixedFormat(str(folder / "sample-word.pdf"), 17)
    print("Word opened and rendered exported DOCX successfully")
finally:
    if document is not None: document.Close(False)
    app.Quit()

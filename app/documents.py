import io

from pypdf import PdfReader


def pdf_to_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def infer_locale(sender: str) -> str:
    domain = sender.rsplit("@", 1)[-1].lower().strip()
    if domain.endswith(".in"):
        return "IN"
    if domain.endswith(".uk"):
        return "GB"
    return "US"

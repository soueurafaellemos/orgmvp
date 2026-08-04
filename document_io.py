from __future__ import annotations

import base64
import io
import mimetypes
from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Iterable

import fitz


@dataclass
class InputDocument:
    name: str
    data: bytes
    mime_type: str


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".json",
    ".html",
    ".xml",
    ".doc",
    ".docx",
    ".rtf",
    ".odt",
    ".ppt",
    ".pptx",
    ".csv",
    ".tsv",
    ".xls",
    ".xlsx",
    ".eml",
}


def guess_mime(name: str, fallback: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(name)
    return guessed or fallback


def to_data_url(doc: InputDocument) -> str:
    encoded = base64.b64encode(doc.data).decode("ascii")
    return f"data:{doc.mime_type};base64,{encoded}"


def extract_eml(data: bytes, original_name: str) -> list[InputDocument]:
    """Transforma um .eml em corpo de e-mail + anexos suportados."""
    message = BytesParser(policy=policy.default).parsebytes(data)
    output: list[InputDocument] = []

    body_parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            content_disposition = part.get_content_disposition()
            content_type = part.get_content_type()

            if content_disposition == "attachment":
                filename = part.get_filename() or "anexo_sem_nome"
                payload = part.get_payload(decode=True) or b""
                suffix = Path(filename).suffix.lower()
                if suffix in SUPPORTED_EXTENSIONS - {".eml"}:
                    output.append(
                        InputDocument(
                            name=filename,
                            data=payload,
                            mime_type=guess_mime(filename),
                        )
                    )
                continue

            if content_type == "text/plain":
                try:
                    body_parts.append(part.get_content())
                except Exception:
                    raw = part.get_payload(decode=True) or b""
                    body_parts.append(raw.decode("utf-8", errors="replace"))
    else:
        try:
            body_parts.append(message.get_content())
        except Exception:
            body_parts.append(data.decode("utf-8", errors="replace"))

    headers = [
        f"Assunto: {message.get('subject', '')}",
        f"De: {message.get('from', '')}",
        f"Para: {message.get('to', '')}",
        f"Data: {message.get('date', '')}",
    ]
    body = "\n".join(headers + ["", *body_parts]).strip()
    if body:
        output.insert(
            0,
            InputDocument(
                name=f"{Path(original_name).stem}_email.txt",
                data=body.encode("utf-8"),
                mime_type="text/plain",
            ),
        )
    return output


def prepare_documents(
    uploaded: Iterable[tuple[str, bytes, str | None]]
) -> list[InputDocument]:
    docs: list[InputDocument] = []
    for name, data, supplied_mime in uploaded:
        suffix = Path(name).suffix.lower()
        if suffix == ".eml":
            docs.extend(extract_eml(data, name))
            continue

        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Formato não suportado: {name}")

        docs.append(
            InputDocument(
                name=name,
                data=data,
                mime_type=supplied_mime or guess_mime(name),
            )
        )
    return docs


def split_pdf(
    doc: InputDocument,
    pages_per_batch: int,
    start_page: int = 1,
    end_page: int | None = None,
) -> list[tuple[InputDocument, int, int]]:
    """Divide PDF em lotes, preservando texto e imagens."""
    source = fitz.open(stream=doc.data, filetype="pdf")
    total_pages = source.page_count

    start_idx = max(0, start_page - 1)
    end_idx = total_pages if end_page is None else min(total_pages, end_page)

    if start_idx >= end_idx:
        raise ValueError("Intervalo de páginas inválido.")

    batches: list[tuple[InputDocument, int, int]] = []
    for first in range(start_idx, end_idx, pages_per_batch):
        last_exclusive = min(first + pages_per_batch, end_idx)
        part = fitz.open()
        part.insert_pdf(source, from_page=first, to_page=last_exclusive - 1)
        part_bytes = part.tobytes(garbage=4, deflate=True)
        part.close()

        first_human = first + 1
        last_human = last_exclusive
        batches.append(
            (
                InputDocument(
                    name=f"{Path(doc.name).stem}_p{first_human}-{last_human}.pdf",
                    data=part_bytes,
                    mime_type="application/pdf",
                ),
                first_human,
                last_human,
            )
        )

    source.close()
    return batches



def render_pdf_page(
    doc: InputDocument,
    page_number: int,
    zoom: float = 1.5,
) -> bytes:
    """Renderiza uma página humana (começando em 1) como PNG."""
    if doc.mime_type != "application/pdf":
        raise ValueError("A fonte selecionada não é um PDF.")

    pdf = fitz.open(stream=doc.data, filetype="pdf")
    try:
        page_index = int(page_number) - 1
        if page_index < 0 or page_index >= pdf.page_count:
            raise ValueError(
                f"Página {page_number} fora do intervalo do PDF."
            )
        page = pdf.load_page(page_index)
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(zoom, zoom),
            alpha=False,
        )
        return pixmap.tobytes("png")
    finally:
        pdf.close()

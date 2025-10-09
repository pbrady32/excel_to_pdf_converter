"""FastAPI application for generating client worksheet PDFs."""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthContext, AuthError, verify_token
from .excel import ExcelParsingError, get_client_name_and_items
from .pdf_build import PDFBuildError, build_pdf
from .storage import StorageError, signed_url, upload_bytes

app = FastAPI(title="Client Worksheet Generator")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


STATIC_DIR = BASE_DIR / "static"
CONFIG_DIR = BASE_DIR / "config"
LAYOUT_PATH = CONFIG_DIR / "layout.yaml"
OPTIONS_PATH = CONFIG_DIR / "options.yaml"


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Unauthorized") -> None:
        super().__init__(status_code=401, detail=detail)


async def authenticate(request: Request) -> AuthContext:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer", "").strip()
    try:
        return verify_token(token)
    except AuthError as exc:
        raise UnauthorizedError(str(exc)) from exc


def load_layout_config() -> dict:
    with open(LAYOUT_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_options_config() -> dict:
    with open(OPTIONS_PATH, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _read_static_page(filename: str) -> HTMLResponse:
    path = STATIC_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found")
    return HTMLResponse(content=path.read_text(encoding="utf-8"))


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    return _read_static_page("index.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page() -> HTMLResponse:
    return _read_static_page("login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page() -> HTMLResponse:
    return _read_static_page("register.html")


@app.post("/generate")
async def generate(
    file: UploadFile = File(...),
    auth: Annotated[AuthContext, Depends(authenticate)] = None,
):
    del auth  # context currently unused but ensures auth executed
    if not file.filename:
        raise HTTPException(status_code=400, detail="File upload is required")

    try:
        contents = await file.read()
    finally:
        await file.close()

    tmp_path = Path("/tmp") / file.filename
    tmp_path.write_bytes(contents)

    try:
        client_name, tax_year, items = get_client_name_and_items(tmp_path)
    except ExcelParsingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    layout_cfg = load_layout_config()
    options_cfg = load_options_config()

    try:
        layout_cfg_with_year = dict(layout_cfg)
        layout_cfg_with_year["tax_year"] = tax_year
        print(f"Layout config with year: {layout_cfg_with_year}")
        pdf_bytes, page_count = build_pdf(client_name, items, layout_cfg_with_year, options_cfg)
    except PDFBuildError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    now = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    safe_name = client_name.lower().replace(" ", "_").replace("/", "-")
    destination = f"worksheets/{safe_name}_{now}.pdf"

    try:
        upload_bytes(pdf_bytes, destination)
        url = signed_url(destination)
    except StorageError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return JSONResponse(
        {
            "ok": True,
            "download_url": url,
            "items": len(items),
            "page_count": page_count,
            "filename": destination,
            "tax_year": tax_year,
        }
    )


@app.get("/healthz")
async def healthcheck() -> dict:
    return {"status": "ok"}

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

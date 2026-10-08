from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .db import get_db
from .excel_import import SEED_XLSX, import_excel, seed_if_needed
from .pdf_extract import PdfExtractError
from . import services

STATIC = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed_if_needed()
    yield


app = FastAPI(title="Weekplanning", docs_url="/api/docs", lifespan=lifespan)


def db():
    return get_db()


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/machines")
def machines():
    return services.list_machines(db())


@app.get("/api/profiles")
def profiles(q: str = ""):
    return services.list_profiles(db(), q=q)


class ProfileIn(BaseModel):
    number: str
    notes: str = ""
    comet_followup: str | None = None
    machines: dict = Field(default_factory=dict)


@app.post("/api/profiles")
def create_or_update_profile(body: ProfileIn):
    try:
        return services.upsert_profile(
            db(), body.number, body.notes, body.comet_followup, body.machines
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.put("/api/profiles/{profile_id}")
def update_profile(profile_id: int, body: ProfileIn):
    row = db().fetchone("SELECT number FROM profiles WHERE id = ?", (profile_id,))
    if not row:
        raise HTTPException(404, "Profiel niet gevonden")
    try:
        return services.upsert_profile(
            db(), body.number, body.notes, body.comet_followup, body.machines
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/api/projects")
def projects():
    return services.list_projects(db())


@app.get("/api/projects/{project_id}")
def project(project_id: int):
    try:
        return services.get_project(db(), project_id)
    except KeyError:
        raise HTTPException(404, "Project niet gevonden")


class LineQty(BaseModel):
    aantal: int


class LineIn(BaseModel):
    profile_number: str
    aantal: int = 1


@app.patch("/api/lines/{line_id}")
def patch_line(line_id: int, body: LineQty):
    try:
        return services.update_line_qty(db(), line_id, body.aantal)
    except KeyError:
        raise HTTPException(404, "Regel niet gevonden")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/projects/{project_id}/lines")
def add_line(project_id: int, body: LineIn):
    try:
        services.get_project(db(), project_id)
        return services.add_line(db(), project_id, body.profile_number, body.aantal)
    except KeyError:
        raise HTTPException(404, "Project niet gevonden")
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.delete("/api/lines/{line_id}")
def delete_line(line_id: int):
    try:
        return services.delete_line(db(), line_id)
    except KeyError:
        raise HTTPException(404, "Regel niet gevonden")


@app.post("/api/import/pdf")
async def import_pdf(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Leeg bestand")
    try:
        return services.import_pdf(db(), data, file.filename or "upload.pdf")
    except PdfExtractError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/import/excel")
async def reimport_excel(file: UploadFile | None = File(None)):
    if file is not None:
        from tempfile import NamedTemporaryFile

        raw = await file.read()
        tmp = NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.write(raw)
        tmp.close()
        result = import_excel(Path(tmp.name), db=db())
        db().commit()
        return result
    result = import_excel(SEED_XLSX, db=db())
    db().commit()
    return result


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")

from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Initialize FastAPI early so decorators below can reference it
app = FastAPI(title="Reports API", version="0.2.0")

# Allow local Streamlit frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import n8n integration
from .n8n_integration import report_generator, n8n_manager

@app.get("/health")
def health() -> Dict[str, Any]:
    return {"ok": True}

# --- S3 integration (list and presign) ---
import boto3
from botocore.client import Config as BotoConfig

S3_BUCKET = os.getenv("S3_BUCKET", "case-reports")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

def s3_client():
    return boto3.client(
        "s3",
        region_name=AWS_REGION,
        config=BotoConfig(signature_version="s3v4"),
    )

def s3_list_versions(case_id: str) -> list[str]:
    prefix = f"reports/{case_id}/"
    client = s3_client()
    paginator = client.get_paginator("list_objects_v2")
    versions: set[str] = set()
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            key = cp.get("Prefix", "")
            # key like reports/<case_id>/<report_id>/
            parts = key.strip("/").split("/")
            if len(parts) >= 3:
                versions.add(parts[2])
    return sorted(list(versions), reverse=True)

def s3_list_cases() -> list[str]:
    client = s3_client()
    cases: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            name = cp.get("Prefix", "").strip("/")
            if not name:
                continue
            # only 4-digit numeric case ids for now
            if name.isdigit() and len(name) == 4:
                cases.append(name)
    return sorted(cases)

def s3_presign(key: str, expires: int = 900) -> str:
    return s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )

@app.get("/s3/{case_id}/versions")
def api_s3_versions(case_id: str) -> Dict[str, Any]:
    return {"case_id": case_id, "versions": s3_list_versions(case_id)}

@app.get("/s3/cases")
def api_s3_cases() -> Dict[str, Any]:
    return {"cases": s3_list_cases()}

@app.get("/s3/{case_id}/{report_id}/assets")
def api_s3_assets(case_id: str, report_id: str) -> Dict[str, Any]:
    """
    Flexible S3 layout support.
    Supports either:
      reports/{case_id}/{report_id}/...
    or the observed bucket layout:
      {case_id}/Output/*.pdf  (generated)
      {case_id}/Ground Truth/* or GroundTruth/* (ground truth)
      {case_id}/pages/* (optional pages)
    """
    response: Dict[str, Any] = {"case_id": case_id, "report_id": report_id}
    client = s3_client()

    def newest_under(prefix: str, exts: tuple[str, ...]) -> str | None:
        paginator = client.get_paginator("list_objects_v2")
        newest_key = None
        newest_time = None
        for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj.get("Key", "")
                if not key or key.endswith("/"):
                    continue
                if not key.lower().endswith(exts):
                    continue
                lm = obj.get("LastModified")
                if newest_time is None or (lm and lm > newest_time):
                    newest_time = lm
                    newest_key = key
        return newest_key

    # Try standard layout first
    base1 = f"reports/{case_id}/{report_id}"
    gt1 = newest_under(f"{base1}/", ("ground_truth.pdf",))
    gen_html1 = newest_under(f"{base1}/", ("generated.html",))
    gen_pdf1 = newest_under(f"{base1}/", ("generated.pdf",))

    # Try observed layout
    base2 = f"{case_id}/"
    gt2 = None
    for p in (f"{base2}Ground Truth/", f"{base2}GroundTruth/"):
        gt2 = newest_under(p, (".pdf", ".docx")) or gt2
    gen2 = newest_under(f"{base2}Output/", (".pdf", ".html"))

    # Prefer standard if present, else observed
    if gt1:
        response["ground_truth_pdf"] = s3_presign(gt1)
    elif gt2:
        # Might be docx; the UI can offer download, not inline view
        response["ground_truth"] = s3_presign(gt2)
    if gen_html1:
        response["generated_html"] = s3_presign(gen_html1)
    if gen_pdf1:
        response["generated_pdf"] = s3_presign(gen_pdf1)
    if not gen_html1 and not gen_pdf1 and gen2:
        if gen2.lower().endswith(".html"):
            response["generated_html"] = s3_presign(gen2)
        else:
            response["generated_pdf"] = s3_presign(gen2)

    # Optional comparison under standard layout
    comps: list[str] = []
    comp_prefix = f"{base1}/comparison/"
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=comp_prefix):
        for obj in page.get("Contents", []):
            key = obj.get("Key", "")
            if not key or key.endswith("/"):
                continue
            name = key.split("/")[-1]
            version = name.rsplit(".", 1)[0]
            if version not in comps:
                comps.append(version)
    response["comparison_versions"] = sorted(comps, reverse=True)
    return response

@app.get("/s3/{case_id}/{report_id}/comparison/{version}")
def api_s3_comparison(case_id: str, report_id: str, version: str) -> Dict[str, Any]:
    base = f"reports/{case_id}/{report_id}/comparison/{version}"
    client = s3_client()
    # Prefer html then pdf
    for ext in ("html", "pdf"):
        key = f"{base}.{ext}"
        try:
            client.head_object(Bucket=S3_BUCKET, Key=key)
            return {"url": s3_presign(key), "format": ext}
        except Exception:
            continue
    raise HTTPException(status_code=404, detail="Comparison version not found")


DB_PATH = Path(os.getenv("REPORTS_DB", "reports.db")).resolve()
ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts")).resolve()
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


# --- Pydantic models (defined BEFORE route decorators) ---
class ReportIn(BaseModel):
    case_id: str
    email: Optional[str] = None
    status: Optional[str] = "queued"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    s3_key: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ReportOut(BaseModel):
    id: int
    case_id: str
    email: Optional[str]
    status: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    s3_key: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    checksum: Optional[str]
    metadata: Optional[Dict[str, Any]]


class UserIn(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    created_at: str


class CycleIn(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    case_id: str
    status: Optional[str] = "processing"
    metadata: Optional[Dict[str, Any]] = None


class CycleOut(BaseModel):
    id: int
    user_id: int
    case_id: str
    status: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    metadata: Optional[Dict[str, Any]]


class FileOut(BaseModel):
    id: int
    cycle_id: int
    kind: Optional[str]
    file_name: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    checksum: Optional[str]
    created_at: Optional[str]


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              case_id TEXT NOT NULL,
              email TEXT,
              status TEXT,
              started_at TEXT,
              finished_at TEXT,
              s3_key TEXT,
              file_path TEXT,
              file_size INTEGER,
              checksum TEXT,
              metadata TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reports_case ON reports(case_id)")
        # New normalized schema
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE,
              email TEXT,
              full_name TEXT,
              created_at TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_cycles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              case_id TEXT NOT NULL,
              status TEXT,
              started_at TEXT,
              finished_at TEXT,
              metadata TEXT,
              FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cycles_user ON report_cycles(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cycles_case ON report_cycles(case_id)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_files (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              cycle_id INTEGER NOT NULL,
              kind TEXT,
              file_name TEXT,
              file_path TEXT,
              file_size INTEGER,
              checksum TEXT,
              created_at TEXT,
              FOREIGN KEY(cycle_id) REFERENCES report_cycles(id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_cycle ON report_files(cycle_id)")
        conn.commit()
    finally:
        conn.close()


# --- Users ---
@app.post("/users", response_model=UserOut)
def upsert_user(user: UserIn) -> UserOut:
    conn = get_conn()
    try:
        now = datetime.utcnow().isoformat()
        existing = conn.execute("SELECT * FROM users WHERE username=?", (user.username,)).fetchone()
        if existing:
            conn.execute(
                "UPDATE users SET email=COALESCE(?, email), full_name=COALESCE(?, full_name) WHERE username=?",
                (user.email, user.full_name, user.username),
            )
        else:
            conn.execute(
                "INSERT INTO users (username, email, full_name, created_at) VALUES (?, ?, ?, ?)",
                (user.username, user.email, user.full_name, now),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE username=?", (user.username,)).fetchone()
        assert row is not None
        return UserOut(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            created_at=row["created_at"],
        )
    finally:
        conn.close()


@app.get("/users/{username}", response_model=UserOut)
def get_user(username: str) -> UserOut:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        return UserOut(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            full_name=row["full_name"],
            created_at=row["created_at"],
        )
    finally:
        conn.close()


# --- Report cycles ---
@app.post("/cycles", response_model=CycleOut)
def create_cycle(cycle: CycleIn) -> CycleOut:
    conn = get_conn()
    try:
        user_id = _ensure_user(conn, cycle.username, cycle.user_id, None, None)
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO report_cycles (user_id, case_id, status, started_at, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, cycle.case_id, cycle.status, now, json.dumps(cycle.metadata or {})),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM report_cycles WHERE user_id=? AND case_id=? ORDER BY id DESC LIMIT 1",
            (user_id, cycle.case_id),
        ).fetchone()
        assert row is not None
        return CycleOut(
            id=row["id"],
            user_id=row["user_id"],
            case_id=row["case_id"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )
    finally:
        conn.close()


@app.get("/users/{username}/cycles", response_model=List[CycleOut])
def list_cycles(username: str, limit: int = 20) -> List[CycleOut]:
    conn = get_conn()
    try:
        user_row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if not user_row:
            return []
        uid = int(user_row[0])
        rows = conn.execute(
            "SELECT * FROM report_cycles WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (uid, limit * 2),
        ).fetchall()
        result: List[CycleOut] = []
        for r in rows:
            meta = json.loads(r["metadata"]) if r["metadata"] else None
            # Skip demo/seeded cycles
            if isinstance(meta, dict) and meta.get("source") == "seed":
                continue
            result.append(
                CycleOut(
                    id=r["id"],
                    user_id=r["user_id"],
                    case_id=r["case_id"],
                    status=r["status"],
                    started_at=r["started_at"],
                    finished_at=r["finished_at"],
                    metadata=meta,
                )
            )
            if len(result) >= limit:
                break
        return result
    finally:
        conn.close()


# --- Files ---
@app.get("/cycles/{cycle_id}/files", response_model=List[FileOut])
def list_files(cycle_id: int) -> List[FileOut]:
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM report_files WHERE cycle_id=? ORDER BY id", (cycle_id,)).fetchall()
        out: List[FileOut] = []
        for r in rows:
            out.append(
                FileOut(
                    id=r["id"],
                    cycle_id=r["cycle_id"],
                    kind=r["kind"],
                    file_name=r["file_name"],
                    file_path=r["file_path"],
                    file_size=r["file_size"],
                    checksum=r["checksum"],
                    created_at=r["created_at"],
                )
            )
        return out
    finally:
        conn.close()


# --- Cycle details & updates ---
@app.get("/cycles/{cycle_id}", response_model=CycleOut)
def get_cycle(cycle_id: int) -> CycleOut:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM report_cycles WHERE id=?", (cycle_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cycle not found")
        return CycleOut(
            id=row["id"],
            user_id=row["user_id"],
            case_id=row["case_id"],
            status=row["status"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )
    finally:
        conn.close()


class CyclePatch(BaseModel):
    status: Optional[str] = None
    finished_at: Optional[str] = None
    accuracy_score: Optional[float] = None
    key_differences: Optional[int] = None
    processing_seconds: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


@app.patch("/cycles/{cycle_id}", response_model=CycleOut)
def update_cycle(cycle_id: int, patch: CyclePatch) -> CycleOut:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM report_cycles WHERE id=?", (cycle_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Cycle not found")
        # merge metadata
        existing_meta: Dict[str, Any] = {}
        if row["metadata"]:
            try:
                existing_meta = json.loads(row["metadata"]) or {}
            except Exception:
                existing_meta = {}
        # attach metrics if provided
        if patch.accuracy_score is not None:
            existing_meta["accuracy_score"] = patch.accuracy_score
        if patch.key_differences is not None:
            existing_meta["key_differences"] = patch.key_differences
        if patch.processing_seconds is not None:
            existing_meta["processing_seconds"] = patch.processing_seconds
        if patch.metadata:
            existing_meta.update(patch.metadata)

        conn.execute(
            "UPDATE report_cycles SET status=COALESCE(?, status), finished_at=COALESCE(?, finished_at), metadata=? WHERE id=?",
            (patch.status, patch.finished_at, json.dumps(existing_meta), cycle_id),
        )
        conn.commit()
        return get_cycle(cycle_id)
    finally:
        conn.close()


@app.post("/cycles/{cycle_id}/files", response_model=FileOut)
def upload_cycle_file(
    cycle_id: int,
    file: UploadFile = File(...),
    kind: Optional[str] = Form(None),
) -> FileOut:
    suffix = Path(file.filename or "artifact.pdf").suffix
    safe_name = f"cycle{cycle_id}_{int(datetime.utcnow().timestamp())}{suffix}"
    target = ARTIFACTS_DIR / safe_name
    with target.open("wb") as out:
        out.write(file.file.read())
    size = target.stat().st_size

    conn = get_conn()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO report_files (cycle_id, kind, file_name, file_path, file_size, checksum, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (cycle_id, kind, file.filename, str(target), size, None, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM report_files WHERE cycle_id=? ORDER BY id DESC LIMIT 1",
            (cycle_id,),
        ).fetchone()
        assert row is not None
        return FileOut(
            id=row["id"],
            cycle_id=row["cycle_id"],
            kind=row["kind"],
            file_name=row["file_name"],
            file_path=row["file_path"],
            file_size=row["file_size"],
            checksum=row["checksum"],
            created_at=row["created_at"],
        )
    finally:
        conn.close()


@app.get("/files/{file_id}/download")
def download_file(file_id: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM report_files WHERE id=?", (file_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="File not found")
        path = row["file_path"]
        if not path or not Path(path).exists():
            raise HTTPException(status_code=404, detail="File missing on server")
        filename = Path(path).name
        # Serve PDFs inline so they can render in iframe on the Results page
        if filename.lower().endswith(".pdf"):
            return FileResponse(
                path=path,
                filename=filename,
                media_type="application/pdf",
                headers={"Content-Disposition": f"inline; filename=\"{filename}\""},
            )
        return FileResponse(path=path, filename=filename)
    finally:
        conn.close()
class ReportIn(BaseModel):
    case_id: str
    email: Optional[str] = None
    status: Optional[str] = "queued"
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    s3_key: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    checksum: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ReportOut(BaseModel):
    id: int
    case_id: str
    email: Optional[str]
    status: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    s3_key: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    checksum: Optional[str]
    metadata: Optional[Dict[str, Any]]


class UserIn(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str]
    full_name: Optional[str]
    created_at: str


class CycleIn(BaseModel):
    username: Optional[str] = None
    user_id: Optional[int] = None
    case_id: str
    status: Optional[str] = "processing"
    metadata: Optional[Dict[str, Any]] = None


class CycleOut(BaseModel):
    id: int
    user_id: int
    case_id: str
    status: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    metadata: Optional[Dict[str, Any]]


class FileOut(BaseModel):
    id: int
    cycle_id: int
    kind: Optional[str]
    file_name: Optional[str]
    file_path: Optional[str]
    file_size: Optional[int]
    checksum: Optional[str]
    created_at: Optional[str]


 


@app.on_event("startup")
def _startup() -> None:  # noqa: D401
    init_db()


def row_to_out(row: sqlite3.Row) -> ReportOut:
    metadata_obj = None
    if row["metadata"]:
        try:
            metadata_obj = json.loads(row["metadata"])  # type: ignore[assignment]
        except Exception:
            metadata_obj = None
    return ReportOut(
        id=row["id"],
        case_id=row["case_id"],
        email=row["email"],
        status=row["status"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        s3_key=row["s3_key"],
        file_path=row["file_path"],
        file_size=row["file_size"],
        checksum=row["checksum"],
        metadata=metadata_obj,
    )


def _ensure_user(conn: sqlite3.Connection, username: Optional[str], user_id: Optional[int], email: Optional[str], full_name: Optional[str]) -> int:
    if user_id:
        return int(user_id)
    if not username:
        raise HTTPException(status_code=400, detail="username or user_id required")
    row = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    if row:
        return int(row[0])
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO users (username, email, full_name, created_at) VALUES (?, ?, ?, ?)",
        (username, email, full_name, now),
    )
    conn.commit()
    created = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    assert created is not None
    return int(created[0])


@app.post("/reports", response_model=ReportOut)
def create_or_update_report(report: ReportIn) -> ReportOut:
    now = datetime.utcnow().isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO reports (case_id, email, status, started_at, finished_at, s3_key, file_path, file_size, checksum, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report.case_id,
                report.email,
                report.status,
                report.started_at or now,
                report.finished_at,
                report.s3_key,
                report.file_path,
                report.file_size,
                report.checksum,
                json.dumps(report.metadata or {}),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM reports WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (report.case_id,),
        ).fetchone()
        assert row is not None
        return row_to_out(row)
    finally:
        conn.close()


@app.get("/reports/{case_id}", response_model=ReportOut)
def get_latest_report(case_id: str) -> ReportOut:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM reports WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        return row_to_out(row)
    finally:
        conn.close()


@app.get("/reports/{case_id}/history", response_model=List[ReportOut])
def get_history(case_id: str) -> List[ReportOut]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM reports WHERE case_id=? ORDER BY id DESC",
            (case_id,),
        ).fetchall()
        return [row_to_out(r) for r in rows]
    finally:
        conn.close()


@app.post("/reports/{case_id}/artifact", response_model=ReportOut)
def upload_artifact(
    case_id: str,
    file: UploadFile = File(...),
    email: Optional[str] = Form(None),
) -> ReportOut:
    suffix = Path(file.filename or "artifact.bin").suffix
    safe_name = f"{case_id}_{int(datetime.utcnow().timestamp())}{suffix}"
    target = ARTIFACTS_DIR / safe_name
    with target.open("wb") as out:
        out.write(file.file.read())
    size = target.stat().st_size

    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO reports (case_id, email, status, started_at, finished_at, s3_key, file_path, file_size, checksum, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                case_id,
                email,
                "done",
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
                None,
                str(target),
                size,
                None,
                json.dumps({"source": "upload"}),
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM reports WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        assert row is not None
        return row_to_out(row)
    finally:
        conn.close()


@app.get("/reports/{case_id}/download")
def download(case_id: str):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM reports WHERE case_id=? ORDER BY id DESC LIMIT 1",
            (case_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Report not found")
        file_path = row["file_path"]
        if file_path and Path(file_path).exists():
            return FileResponse(path=file_path, filename=Path(file_path).name)
        s3_key = row["s3_key"]
        if s3_key:
            # Placeholder: when S3 enabled, return a presigned URL or redirect
            return JSONResponse({"s3_key": s3_key, "note": "Use presigned URL in S3 mode."})
        raise HTTPException(status_code=404, detail="No artifact available")
    finally:
        conn.close()


# n8n Workflow Integration Endpoints
@app.post("/n8n/generate-report")
async def generate_medical_report(patient_id: str, username: str = None) -> Dict[str, Any]:
    """
    Triggers the complete medical report generation workflow via n8n.
    
    Args:
        patient_id: The patient ID to generate report for
        username: The username requesting the report
        
    Returns:
        Dict containing report generation status and details
    """
    try:
        result = await report_generator.generate_complete_report(patient_id, username)
        
        # Store the report generation request in the database
        conn = get_conn()
        try:
            conn.execute(
                """
                INSERT INTO reports (case_id, email, status, started_at, metadata)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    patient_id,
                    username,
                    "processing",
                    datetime.utcnow().isoformat(),
                    json.dumps({
                        "source": "n8n_workflow",
                        "report_id": result.get("report_id"),
                        "workflow_data": result
                    }),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@app.get("/n8n/report-status/{report_id}")
def get_report_status(report_id: str) -> Dict[str, Any]:
    """
    Gets the status of a report generation process.
    
    Args:
        report_id: The report ID
        
    Returns:
        Dict containing report status
    """
    try:
        status = report_generator.get_report_status(report_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get report status: {str(e)}")


@app.get("/n8n/workflow-status/{execution_id}")
def get_workflow_status(execution_id: str) -> Dict[str, Any]:
    """
    Gets the status of a specific n8n workflow execution.
    
    Args:
        execution_id: The execution ID from the workflow
        
    Returns:
        Dict containing workflow status
    """
    try:
        status = n8n_manager.get_workflow_status(execution_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")


@app.get("/n8n/workflow-result/{execution_id}")
def get_workflow_result(execution_id: str) -> Dict[str, Any]:
    """
    Gets the result of a completed n8n workflow execution.
    
    Args:
        execution_id: The execution ID from the workflow
        
    Returns:
        Dict containing workflow results
    """
    try:
        result = n8n_manager.get_workflow_result(execution_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflow result: {str(e)}")


@app.get("/n8n/download-report/{report_id}")
def download_generated_report(report_id: str):
    """
    Downloads a generated medical report.
    
    Args:
        report_id: The report ID
        
    Returns:
        File response with the report
    """
    try:
        report_file = report_generator.get_report_file(report_id)
        if report_file and report_file.exists():
            return FileResponse(
                path=str(report_file), 
                filename=report_file.name,
                media_type="application/pdf" if report_file.suffix == ".pdf" else "text/html"
            )
        else:
            raise HTTPException(status_code=404, detail="Report file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to download report: {str(e)}")


# Optional: admin cleanup to remove seeded demo data
@app.delete("/admin/cleanup_seeds")
def cleanup_seeds() -> Dict[str, int]:
    conn = get_conn()
    try:
        # Find seeded cycles
        rows = conn.execute("SELECT id FROM report_cycles WHERE metadata LIKE '%\"source\": \"seed\"%'").fetchall()
        ids = [int(r[0]) for r in rows]
        # Delete associated files
        for cid in ids:
            conn.execute("DELETE FROM report_files WHERE cycle_id=?", (cid,))
        conn.execute("DELETE FROM report_cycles WHERE id IN (" + ",".join([str(i) for i in ids]) + ")") if ids else None
        conn.commit()
        return {"deleted_cycles": len(ids)}
    finally:
        conn.close()

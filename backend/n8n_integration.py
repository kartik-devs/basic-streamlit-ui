"""
n8n Workflow Integration Module

This module handles the integration between the web UI and n8n workflows
for medical report generation. It manages webhook calls, status tracking,
and result retrieval.
"""

import os
import json
import requests
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class N8nWorkflowManager:
    """Manages n8n workflow execution and status tracking."""
    
    def __init__(self, n8n_base_url: str = None, api_key: str = None):
        self.n8n_base_url = n8n_base_url or os.getenv("N8N_BASE_URL", "http://localhost:5678")
        self.api_key = api_key or os.getenv("N8N_API_KEY")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-N8N-API-KEY": self.api_key})
        # Optional explicit cancel webhook URL (preferred when API stop endpoint not available)
        self.cancel_webhook_url = os.getenv("N8N_CANCEL_WEBHOOK_URL")
        # Trigger webhook URL (used to start the main workflow if API trigger is not available)
        self.trigger_webhook_url = os.getenv("N8N_TRIGGER_WEBHOOK_URL") or os.getenv("N8N_WEBHOOK_URL")
        # Main workflow id (string or number), used to identify executions
        self.main_workflow_id = os.getenv("N8N_MAIN_WORKFLOW_ID")
    
    def trigger_ocr_workflow(self, patient_id: str, s3_key: str = None) -> Dict[str, Any]:
        """
        Triggers the OCR Text Extraction workflow.
        
        Args:
            patient_id: The patient ID to process
            s3_key: Optional S3 key for the document
            
        Returns:
            Dict containing workflow execution details
        """
        webhook_url = f"{self.n8n_base_url}/webhook/ocr-text-extraction"
        
        payload = {
            "patient_id": patient_id,
            "s3_key": s3_key,
            "timestamp": datetime.now().isoformat(),
            "source": "web_ui"
        }
        
        try:
            response = self.session.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            out = {
                "success": True,
                "execution_id": response.json().get("executionId"),
                "status": "triggered",
                "timestamp": datetime.now().isoformat()
            }
            # Persist execution id if present
            try:
                if out.get("execution_id"):
                    _store_execution_id(patient_id, out["execution_id"])
            except Exception:
                pass
            return out
        except Exception as e:
            logger.error(f"Failed to trigger OCR workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def trigger_section_workflow(self, section_number: int, patient_id: str, 
                               input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers a specific section workflow.
        
        Args:
            section_number: The section number (1-8)
            patient_id: The patient ID
            input_data: Input data for the section
            
        Returns:
            Dict containing workflow execution details
        """
        webhook_url = f"{self.n8n_base_url}/webhook/section-{section_number}"
        
        payload = {
            "patient_id": patient_id,
            "section_number": section_number,
            "input_data": input_data,
            "timestamp": datetime.now().isoformat(),
            "source": "web_ui"
        }
        
        try:
            response = self.session.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            out = {
                "success": True,
                "execution_id": response.json().get("executionId"),
                "status": "triggered",
                "timestamp": datetime.now().isoformat()
            }
            try:
                if out.get("execution_id"):
                    _store_execution_id(patient_id, out["execution_id"])
            except Exception:
                pass
            return out
        except Exception as e:
            logger.error(f"Failed to trigger Section {section_number} workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def trigger_complete_report_workflow(self, patient_id: str, 
                                       sections_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers the complete report generation workflow.
        
        Args:
            patient_id: The patient ID
            sections_data: Data from all sections
            
        Returns:
            Dict containing workflow execution details
        """
        webhook_url = f"{self.n8n_base_url}/webhook/complete-report-generation"
        
        payload = {
            "patient_id": patient_id,
            "sections_data": sections_data,
            "timestamp": datetime.now().isoformat(),
            "source": "web_ui"
        }
        
        try:
            response = self.session.post(webhook_url, json=payload, timeout=30)
            response.raise_for_status()
            out = {
                "success": True,
                "execution_id": response.json().get("executionId"),
                "status": "triggered",
                "timestamp": datetime.now().isoformat()
            }
            try:
                if out.get("execution_id"):
                    _store_execution_id(patient_id, out["execution_id"])
            except Exception:
                pass
            return out
        except Exception as e:
            logger.error(f"Failed to trigger complete report workflow: {e}")
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def get_workflow_status(self, execution_id: str) -> Dict[str, Any]:
        """
        Gets the status of a workflow execution.
        
        Args:
            execution_id: The execution ID from the workflow
            
        Returns:
            Dict containing workflow status
        """
        status_url = f"{self.n8n_base_url}/api/v1/executions/{execution_id}"
        
        try:
            response = self.session.get(status_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get workflow status: {e}")
            return {
                "success": False,
                "error": str(e),
                "status": "unknown"
            }
    
    def get_workflow_result(self, execution_id: str) -> Dict[str, Any]:
        """
        Gets the result of a completed workflow execution.
        
        Args:
            execution_id: The execution ID from the workflow
            
        Returns:
            Dict containing workflow results
        """
        result_url = f"{self.n8n_base_url}/api/v1/executions/{execution_id}/data"
        
        try:
            response = self.session.get(result_url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get workflow result: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def trigger_main_workflow_and_capture_execution(self, case_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Start the main workflow via webhook (or API if available) and attempt to capture execution id.
        Returns a dict with at least { started: bool, success: bool, execution_id?: str, error?: str }.
        Execution id capture depends on N8N_API_KEY and N8N_MAIN_WORKFLOW_ID.
        """
        payload = payload or {"case_id": case_id}
        # Enforce case_id consistency; drop patient_id in favor of case_id
        if "patient_id" in payload and not payload.get("case_id"):
            payload["case_id"] = payload.get("patient_id")
        if "patient_id" in payload:
            try:
                del payload["patient_id"]
            except Exception:
                pass
        exec_id: Optional[str] = None
        started = False
        # Step 1: Start the workflow via webhook if configured
        try:
            if self.trigger_webhook_url:
                # Enforce case_id key in payload for consistency
                if "case_id" not in payload:
                    payload = {**payload, "case_id": case_id}
                r = self.session.post(self.trigger_webhook_url, json=payload, timeout=10)
                r.raise_for_status()
                started = True
        except Exception as e:
            # Continue; we may still be able to detect execution if it started
            logger.warning(f"Trigger webhook failed: {e}")
        # Step 2: Poll executions API and pick latest running for main workflow
        try:
            if not (self.api_key and self.main_workflow_id):
                return {"success": started, "started": started, "error": "N8N_API_KEY and N8N_MAIN_WORKFLOW_ID required"}
            # Query recent executions then detect running by finished==False or no stoppedAt
            urls = [
                f"{self.n8n_base_url}/api/v1/executions?limit=25",
            ]
            import time
            for _ in range(10):  # short poll window ~3-4s
                for url in urls:
                    try:
                        resp = self.session.get(url, timeout=5)
                        if not resp.ok:
                            continue
                        data = resp.json()
                        items: List[Dict[str, Any]] = data if isinstance(data, list) else data.get("data") or data.get("items") or []
                        # Normalize workflow id compare
                        target = str(self.main_workflow_id)
                        candidates = []
                        for it in items:
                            wid = it.get("workflowId") or it.get("workflow_id")
                            if wid is not None and str(wid) == target:
                                # running only when finished == False AND no stoppedAt
                                finished = it.get("finished")
                                stopped = it.get("stoppedAt") or it.get("stopped_at")
                                if (finished is False) and (not stopped):
                                    candidates.append(it)
                        if candidates:
                            # Pick the newest by id or startedAt
                            def _key(it):
                                return it.get("id") or it.get("startedAt") or it.get("started_at") or 0
                            latest = sorted(candidates, key=_key, reverse=True)[0]
                            e = latest.get("id") or latest.get("executionId") or latest.get("execution_id")
                            if e:
                                exec_id = str(e)
                                _store_execution_id(case_id, exec_id)
                                return {"success": True, "started": True, "execution_id": exec_id}
                    except Exception:
                        continue
                time.sleep(0.3)
            # Could not capture exec id, but report start state
            return {"success": started, "started": started, "error": "could not capture execution id"}
        except Exception as e:
            return {"success": started, "started": started, "error": str(e)}

    def cancel_by_execution_id(self, execution_id: str) -> Dict[str, Any]:
        """Best-effort cancellation by execution id.
        Prefers explicit cancel webhook when configured; otherwise attempts n8n API if available.
        """
        try:
            headers = {"Content-Type": "application/json"}
            # Preferred: explicit cancel webhook
            if self.cancel_webhook_url:
                r = self.session.post(self.cancel_webhook_url, json={"execution_id": execution_id, "action": "cancel"}, timeout=10)
                ok = r.ok
                return {"ok": ok, "via": "webhook", "status": r.status_code}
            # Fallback: attempt n8n API stop endpoint (version dependent)
            # Common patterns across versions (may not exist on all installs)
            candidates = [
                # API v1 endpoints
                ("POST", f"{self.n8n_base_url}/api/v1/executions/{execution_id}/stop"),
                ("DELETE", f"{self.n8n_base_url}/api/v1/executions/{execution_id}"),
                # Legacy REST endpoints (older n8n builds)
                ("POST", f"{self.n8n_base_url}/rest/executions/{execution_id}/stop"),
                ("DELETE", f"{self.n8n_base_url}/rest/executions/{execution_id}"),
            ]
            for method, url in candidates:
                try:
                    if method == "POST":
                        r = self.session.post(url, timeout=10)
                    else:
                        r = self.session.delete(url, timeout=10)
                    if r.ok:
                        return {"ok": True, "via": url, "status": r.status_code}
                except Exception:
                    continue
            return {"ok": False, "error": "no cancel endpoint available"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def cancel_by_case_id(self, case_id: str) -> Dict[str, Any]:
        """Deprecated broad cancel by case. Keep for compatibility but make it a no-op unless an execution id is resolvable.
        """
        try:
            # Fallback: look up last execution id for case and cancel that
            exec_id = _get_last_execution_id(case_id)
            if exec_id:
                return self.cancel_by_execution_id(exec_id)
            return {"ok": False, "error": "no execution id recorded for case"}
        except Exception as e:
            return {"ok": False, "error": str(e)}


class ReportGenerator:
    """Handles the complete report generation process."""
    
    def __init__(self, n8n_manager: N8nWorkflowManager):
        self.n8n_manager = n8n_manager
        self.artifacts_dir = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_complete_report(self, patient_id: str, 
                                     username: str = None) -> Dict[str, Any]:
        """
        Generates a complete medical report for a patient.
        
        Args:
            patient_id: The patient ID
            username: The username requesting the report
            
        Returns:
            Dict containing report generation status and details
        """
        report_id = f"report_{patient_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Step 1: Trigger OCR workflow
            logger.info(f"Starting OCR workflow for patient {patient_id}")
            ocr_result = self.n8n_manager.trigger_ocr_workflow(patient_id)
            
            if not ocr_result["success"]:
                return {
                    "success": False,
                    "error": f"OCR workflow failed: {ocr_result.get('error')}",
                    "report_id": report_id
                }
            
            # Step 2: Trigger section workflows (1-8)
            section_results = {}
            for section_num in range(1, 9):
                logger.info(f"Starting Section {section_num} workflow for patient {patient_id}")
                section_result = self.n8n_manager.trigger_section_workflow(
                    section_num, patient_id, {"report_id": report_id}
                )
                section_results[f"section_{section_num}"] = section_result
            
            # Step 3: Trigger final report generation
            logger.info(f"Starting final report generation for patient {patient_id}")
            final_result = self.n8n_manager.trigger_complete_report_workflow(
                patient_id, {
                    "report_id": report_id,
                    "section_results": section_results,
                    "username": username
                }
            )
            
            return {
                "success": True,
                "report_id": report_id,
                "patient_id": patient_id,
                "ocr_execution_id": ocr_result.get("execution_id"),
                "section_results": section_results,
                "final_execution_id": final_result.get("execution_id"),
                "status": "processing",
                "started_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Report generation failed for patient {patient_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "report_id": report_id,
                "patient_id": patient_id
            }
    
    def get_report_status(self, report_id: str) -> Dict[str, Any]:
        """
        Gets the status of a report generation process.
        
        Args:
            report_id: The report ID
            
        Returns:
            Dict containing report status
        """
        # This would typically check the database for report status
        # For now, return a mock status
        return {
            "report_id": report_id,
            "status": "processing",
            "progress": 75,
            "estimated_completion": (datetime.now() + timedelta(minutes=5)).isoformat()
        }
    
    def get_report_file(self, report_id: str) -> Optional[Path]:
        """
        Gets the generated report file.
        
        Args:
            report_id: The report ID
            
        Returns:
            Path to the report file if it exists
        """
        html_file = self.artifacts_dir / f"{report_id}.html"
        pdf_file = self.artifacts_dir / f"{report_id}.pdf"
        
        if pdf_file.exists():
            return pdf_file
        elif html_file.exists():
            return html_file
        else:
            return None


# Global instance
n8n_manager = N8nWorkflowManager()
report_generator = ReportGenerator(n8n_manager)


# --- Lightweight execution-id persistence helpers (SQLite) ---
_DB_PATH = os.getenv("REPORTS_DB", "reports.db")

def _store_execution_id(case_id: str, execution_id: str) -> None:
    """Store last execution id in reports.metadata for the most recent row of the case."""
    import sqlite3, json as _json
    conn = sqlite3.connect(_DB_PATH)
    try:
        cur = conn.cursor()
        # Ensure table exists minimally
        cur.execute(
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
              metadata TEXT,
              code_version TEXT
            )
            """
        )
        conn.commit()
        # Fetch latest row for case
        row = cur.execute("SELECT id, metadata FROM reports WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        if row:
            rid, meta_text = row
            try:
                meta = _json.loads(meta_text) if meta_text else {}
            except Exception:
                meta = {}
            meta["n8n_execution_id"] = execution_id
            cur.execute("UPDATE reports SET metadata=? WHERE id=?", (_json.dumps(meta), rid))
        else:
            meta = {"n8n_execution_id": execution_id}
            cur.execute(
                "INSERT INTO reports (case_id, status, started_at, metadata) VALUES (?, ?, datetime('now'), ?)",
                (case_id, "processing", _json.dumps(meta)),
            )
        conn.commit()
    finally:
        conn.close()


def _get_last_execution_id(case_id: str) -> Optional[str]:
    import sqlite3, json as _json
    conn = sqlite3.connect(_DB_PATH)
    try:
        row = conn.execute("SELECT metadata FROM reports WHERE case_id=? ORDER BY id DESC LIMIT 1", (case_id,)).fetchone()
        if not row:
            return None
        meta_text = row[0]
        try:
            meta = _json.loads(meta_text) if meta_text else {}
        except Exception:
            meta = {}
        val = meta.get("n8n_execution_id")
        return val if isinstance(val, str) and val else None
    finally:
        conn.close()


# Public helper wrapper for main app
def get_last_execution_id(case_id: str) -> Optional[str]:
    return _get_last_execution_id(case_id)

def store_execution_id(case_id: str, execution_id: str) -> None:
    _store_execution_id(case_id, execution_id)

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
            return {
                "success": True,
                "execution_id": response.json().get("executionId"),
                "status": "triggered",
                "timestamp": datetime.now().isoformat()
            }
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
            return {
                "success": True,
                "execution_id": response.json().get("executionId"),
                "status": "triggered",
                "timestamp": datetime.now().isoformat()
            }
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
            return {
                "success": True,
                "execution_id": response.json().get("executionId"),
                "status": "triggered",
                "timestamp": datetime.now().isoformat()
            }
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

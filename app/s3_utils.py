import boto3
import os
import yaml
from typing import Optional, List, Dict, Any
from botocore.exceptions import ClientError, NoCredentialsError, ReadTimeoutError, EndpointConnectionError
from botocore.config import Config
import streamlit as st
import tempfile
import base64
import subprocess
import io

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed


class S3Manager:
    def __init__(self):
        """Initialize S3 client with credentials from environment or config"""
        self.s3_client = None
        # Try both environment variable names
        self.bucket_name = os.getenv('S3_BUCKET_NAME') or os.getenv('S3_BUCKET') or 'finallcpreports'
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Try to load config file
        config = self._load_config()
        if config:
            self.bucket_name = config.get('s3', {}).get('bucket_name', self.bucket_name)
            self.region = config.get('aws', {}).get('region', self.region)
            aws_access_key = config.get('aws', {}).get('access_key_id')
            aws_secret_key = config.get('aws', {}).get('secret_access_key')
        else:
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        
        # Try to initialize S3 client
        try:
            # Configure robust timeouts/retries to avoid ReadTimeouts on large files
            boto_cfg = Config(
                connect_timeout=10,
                read_timeout=120,
                retries={"max_attempts": 5, "mode": "standard"},
            )
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=self.region,
                config=boto_cfg,
            )
            # Test connection
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except (NoCredentialsError, ClientError) as e:
            st.warning(f"S3 connection failed: {str(e)}")
            self.s3_client = None
    
    def _load_config(self) -> Optional[Dict[str, Any]]:
        """Load S3 configuration from file"""
        config_paths = ['s3_config.yaml', 'config/s3_config.yaml']
        for path in config_paths:
            try:
                if os.path.exists(path):
                    with open(path, 'r') as f:
                        return yaml.safe_load(f)
            except Exception:
                continue
        return None
    
    def get_case_files(self, case_id: str) -> Dict[str, Any]:
        """
        Get files for a specific case ID
        Returns dict with ground_truth, ai_generated_report, and doctor_reports
        """
        if not self.s3_client:
            return {}
        
        try:
            # List objects with case_id prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"{case_id}/"
            )
            
            files = response.get('Contents', [])
            case_files = {
                "ground_truth": None,
                "ai_generated_report": None,
                "doctor_reports": [],
                "redacted_reports": []
            }
            

            
            for file_obj in files:
                key = file_obj['Key']
                
                # Ground truth (original document - mostly Word files)
                if ('GroundTruth' in key) and (key.endswith('.pdf') or key.endswith('.docx')):
                    case_files['ground_truth'] = key
                
                # AI Generated Report (output from n8n workflow)
                elif 'CompleteAIGenerated' in key and key.endswith('.pdf'):
                    case_files['ai_generated_report'] = key
                
                # Doctor/LLM Reports (previous versions for comparison)
                elif 'LLM_As_Doctor' in key and key.endswith('.pdf'):
                    case_files['doctor_reports'].append(key)

            redacted_reports = []
            for file_obj in files:
                key = file_obj["Key"]
                if "redacted" in key.lower() and key.endswith(".pdf"):
                    redacted_reports.append(key)

            if redacted_reports:
                case_files["redacted_reports"] = redacted_reports
            return case_files
            
        except ClientError as e:
            st.error(f"Error fetching case files: {str(e)}")
            return {}
    
    def download_pdf(self, s3_key: str) -> Optional[bytes]:
        """Download PDF from S3 and return as bytes"""
        if not self.s3_client:
            return None
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            return response['Body'].read()
        except ClientError as e:
            st.error(f"Error downloading PDF {s3_key}: {str(e)}")
            return None
    
    def get_file_base64(self, s3_key: str) -> Optional[str]:
        """Get file from S3 as base64 encoded string for iframe display"""
        file_bytes = self.download_file(s3_key)
        if file_bytes:
            return base64.b64encode(file_bytes).decode('utf-8')
        return None
    
    def convert_word_to_pdf(self, word_bytes: bytes) -> Optional[bytes]:
        """Convert Word document to PDF using Python libraries (fastest)"""
        try:
            # Try to import required libraries
            try:
                from docx import Document
                from reportlab.pdfgen import canvas
                from reportlab.lib.pagesizes import letter, A4
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.platypus import SimpleDocTemplate, Paragraph
                from reportlab.lib.units import inch
            except ImportError:
                st.warning("📦 Install required packages: pip install python-docx reportlab")
                return None
            
            # Extract text from Word document
            doc = Document(io.BytesIO(word_bytes))
            text_content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            # Create PDF in memory
            pdf_buffer = io.BytesIO()
            doc_pdf = SimpleDocTemplate(pdf_buffer, pagesize=A4)
            styles = getSampleStyleSheet()
            story = []
            
            # Add text to PDF
            for text in text_content:
                p = Paragraph(text, styles['Normal'])
                story.append(p)
            
            # Build PDF
            doc_pdf.build(story)
            pdf_bytes = pdf_buffer.getvalue()
            pdf_buffer.close()
            
            return pdf_bytes
            
        except Exception as e:
            st.error(f"Error converting Word to PDF: {str(e)}")
            return None
    
    def get_pdf_base64(self, s3_key: str) -> Optional[str]:
        """Get PDF from S3 as base64 encoded string for iframe display (deprecated, use get_file_base64)"""
        return self.get_file_base64(s3_key)
    
    def download_file(self, s3_key: str) -> Optional[bytes]:
        """Download any file from S3 and return as bytes (resilient)."""
        if not self.s3_client:
            return None
        try:
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
            # Stream-read in chunks to avoid long blocking reads
            body = response.get('Body')
            if not body:
                return None
            chunks: list[bytes] = []
            while True:
                data = body.read(1024 * 1024)  # 1MB
                if not data:
                    break
                chunks.append(data)
            return b"".join(chunks)
        except ReadTimeoutError:
            st.warning(f"S3 read timed out for {s3_key}. Skipping this file in export.")
            return None
        except EndpointConnectionError as e:
            st.error(f"S3 endpoint connection error: {e}")
            return None
        except ClientError as e:
            st.error(f"Error downloading file {s3_key}: {str(e)}")
            return None
    
    def list_available_cases(self) -> List[str]:
        """List all available case IDs in S3"""
        if not self.s3_client:
            return []
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Delimiter='/'
            )
            
            cases = []
            for prefix in response.get('CommonPrefixes', []):
                case_prefix = prefix['Prefix']
                if case_prefix.startswith('case_'):
                    case_id = case_prefix.replace('case_', '').replace('/', '')
                    if case_id.isdigit():
                        cases.append(case_id)
            
            return sorted(cases, reverse=True)
            
        except ClientError as e:
            st.error(f"Error listing cases: {str(e)}")
            return []
    



# Global S3 manager instance
s3_manager = S3Manager()


def get_s3_manager() -> S3Manager:
    """Get the global S3 manager instance"""
    return s3_manager


def mock_s3_data_for_demo(case_id: str) -> Dict[str, Any]:
    """
    Mock S3 data for demo purposes when S3 is not available
    This simulates what the real S3 integration would return
    """
    return {
        'ground_truth': f"{case_id}/GroundTruth/{case_id}_LCP_Blanca Ortiz_final draft-5-21-2025 - Copy.docx",
        'ai_generated_report': f"{case_id}/Output/{case_id}-TyronneCraig-CompleteAIGenerated.pdf",
        'doctor_reports': [
            f"{case_id}/Output/202508280904-{case_id}-BlancaOrtiz_LLM_As_Doctor.pdf"
        ]
    }

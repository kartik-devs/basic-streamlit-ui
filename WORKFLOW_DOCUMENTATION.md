# Medical Report Generation System - Workflow Documentation

## System Overview

This system helps doctors and patients involved in legal cases (accidents, medical malpractice, etc.) by automatically generating comprehensive medical reports from patient data stored in S3. The system processes data through multiple AI-powered sections and outputs an HTML report that can be converted to PDF.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web UI        │    │   Backend API   │    │   n8n Workflows │
│   (Streamlit)   │◄──►│   (FastAPI)     │◄──►│   (Automation)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Authentication│    │   Database      │    │   S3 Storage    │
│   & User Mgmt   │    │   (SQLite)      │    │   (Documents)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## User Flow

1. **Authentication**: Users log in through the Streamlit web interface
2. **Case Input**: User enters a 4-digit Case ID (Patient ID)
3. **Workflow Trigger**: Backend triggers n8n workflows for report generation
4. **Progress Tracking**: User can monitor progress in real-time
5. **Report Download**: Final PDF report is available for download

## n8n Workflow Architecture

### 1. OCR Text Extraction Workflow
**Purpose**: Extract and classify text from patient documents

**Input**: Patient ID via webhook
**Process**:
- Retrieves signed URLs and S3 keys for patient documents
- Classifies pages (Printed, Handwritten, Scanned)
- Extracts text using OCR technology
- Tracks classification results in database

**Output**: Processed text data for further analysis

**Key Nodes**:
- `Get Key and URL`: Retrieves S3 document URLs
- `Page Classification`: Classifies document types
- `HTTP Request`: Processes documents through OCR service
- `Page Classification Tracker`: Stores results

### 2. Page Detection for Agents (Optional)
**Purpose**: Identifies relevant pages for each section

**Process**:
- Detects pages for agents and tracks page categories
- Routes specific pages to appropriate section workflows

**Output**: Page categorization data

### 3. Section Generation Workflows (Sections 1-8)

#### Section 1: Table of Contents & Initial Content
- **AI Agent**: Uses Google Gemini Chat Model
- **Process**: Generates table of contents and initial section content
- **Output**: Formatted Section 1 content

#### Section 2: Content Generation with Accuracy Metrics
- **External API**: POST to `http://98.82.36.138:80...`
- **Process**: Generates content and calculates accuracy against ground truth
- **Storage**: Results stored in Airtable
- **Output**: Section 2 content with accuracy metrics

#### Section 3: Patient Intake Data Processing
- **Data Source**: Zoho CRM via Snowflake database
- **AI Model**: Google Gemini Chat Model
- **Process**: Retrieves patient intake data and generates narrative content
- **Output**: Section 3 content based on patient history

#### Section 4: Dual AI Agent Processing
- **AI Models**: Two Google Vertex Chat Models (AI Agent1 & AI Agent2)
- **Process**: Sequential AI processing with memory and tools
- **Accuracy**: Compares with ground truth
- **Output**: Enhanced Section 4 content

#### Sections 5-7: Sequential Content Creation
- **Process**: Sequential content creation and formatting
- **Flow**: Section 5 → Section 6 → Section 7
- **Output**: Formatted content for each section

#### Section 8: Gender-Based Processing
- **Conditional Logic**: Processes based on patient gender
- **Parallel Processing**: Separate workflows for Female and Male patients
- **Combination**: Merges results from both paths
- **Output**: Gender-specific Section 8 content

### 4. Final Step: Report Assembly
**Purpose**: Combines all sections and generates final report

**Process**:
- Combines outputs from all sections
- Applies final formatting
- Compares with ground truth
- Calculates final accuracy metrics
- Generates HTML report
- Converts to PDF

**Output**: Complete medical report in HTML/PDF format

## Web UI Integration

### Backend API Endpoints

#### 1. Report Generation
```http
POST /n8n/generate-report
Parameters:
- patient_id: string (required)
- username: string (optional)

Response:
{
  "success": true,
  "report_id": "report_1234_20241201_143022",
  "patient_id": "1234",
  "ocr_execution_id": "exec_123",
  "section_results": {...},
  "final_execution_id": "exec_456",
  "status": "processing",
  "started_at": "2024-12-01T14:30:22"
}
```

#### 2. Status Checking
```http
GET /n8n/report-status/{report_id}

Response:
{
  "report_id": "report_1234_20241201_143022",
  "status": "processing",
  "progress": 75,
  "estimated_completion": "2024-12-01T14:35:22"
}
```

#### 3. Workflow Status
```http
GET /n8n/workflow-status/{execution_id}

Response:
{
  "execution_id": "exec_123",
  "status": "completed",
  "started_at": "2024-12-01T14:30:22",
  "finished_at": "2024-12-01T14:32:15"
}
```

#### 4. Report Download
```http
GET /n8n/download-report/{report_id}

Response: PDF file download
```

### Frontend Integration

#### Case Report Page (`pages/01_Case_Report.py`)
- User enters 4-digit Case ID
- Triggers n8n workflow via backend API
- Stores workflow data in session state
- Redirects to progress tracking page

#### Generating Report Page (`pages/02_Generating_Report.py`)
- Displays real-time progress of all workflow steps
- Shows status for OCR, Sections 1-8, and Final generation
- Provides manual status refresh
- Auto-redirects to results when complete

#### Results Page (`pages/03_Results.py`)
- Displays generated report
- Provides PDF download functionality
- Shows accuracy metrics and processing time

## Configuration

### Environment Variables

```bash
# n8n Configuration
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_api_key_here

# Backend Configuration
BACKEND_BASE=http://localhost:8000
ARTIFACTS_DIR=./artifacts

# Database Configuration
REPORTS_DB=./reports.db
```

### n8n Webhook URLs

The system expects the following webhook endpoints in n8n:

1. **OCR Text Extraction**: `/webhook/ocr-text-extraction`
2. **Section Workflows**: `/webhook/section-{1-8}`
3. **Complete Report**: `/webhook/complete-report-generation`

## Data Flow

### 1. Initial Request
```
User Input (Case ID) → Web UI → Backend API → n8n Workflow Trigger
```

### 2. Workflow Execution
```
n8n OCR Workflow → Text Extraction → Section Workflows (1-8) → Final Assembly
```

### 3. Result Delivery
```
Generated Report → S3 Storage → Backend API → Web UI → User Download
```

## Error Handling

### Workflow Failures
- Each workflow step has error handling
- Failed steps are logged and reported
- Partial results are preserved
- Retry mechanisms for transient failures

### API Failures
- Timeout handling for long-running operations
- Graceful degradation when n8n is unavailable
- User-friendly error messages
- Fallback to demo mode when needed

## Security Considerations

### Authentication
- User authentication required for all operations
- Session-based authentication with Streamlit
- API key authentication for n8n integration

### Data Privacy
- Patient data encrypted in transit and at rest
- S3 bucket access controls
- Audit logging for all operations
- HIPAA compliance considerations

## Monitoring and Logging

### Workflow Monitoring
- Real-time status tracking
- Progress indicators for each step
- Execution time monitoring
- Error rate tracking

### System Logging
- Structured logging for all operations
- Error tracking and alerting
- Performance metrics collection
- User activity logging

## Deployment

### Prerequisites
- n8n instance running and accessible
- S3 bucket configured for document storage
- Database initialized with proper schema
- All environment variables configured

### Startup Sequence
1. Start n8n workflows
2. Start backend API server
3. Start Streamlit web application
4. Verify all connections

### Health Checks
- n8n workflow availability
- Backend API responsiveness
- Database connectivity
- S3 bucket access

## Troubleshooting

### Common Issues

1. **n8n Connection Failed**
   - Check N8N_BASE_URL configuration
   - Verify n8n instance is running
   - Check firewall/network connectivity

2. **Workflow Timeout**
   - Increase timeout values in configuration
   - Check n8n workflow performance
   - Monitor resource usage

3. **Report Generation Failed**
   - Check S3 bucket permissions
   - Verify patient data exists
   - Review workflow logs

### Debug Commands

```bash
# Check n8n status
curl -X GET "http://localhost:5678/api/v1/health"

# Test webhook
curl -X POST "http://localhost:5678/webhook/ocr-text-extraction" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "1234"}'

# Check backend status
curl -X GET "http://localhost:8000/health"
```

## Future Enhancements

### Planned Features
- Real-time progress updates via WebSocket
- Batch processing for multiple cases
- Advanced error recovery mechanisms
- Enhanced accuracy metrics
- Custom report templates

### Scalability Improvements
- Horizontal scaling of n8n instances
- Database optimization
- Caching layer implementation
- Load balancing for high traffic

## Support and Maintenance

### Regular Maintenance
- Database cleanup and optimization
- Log rotation and archival
- Security updates and patches
- Performance monitoring and tuning

### Backup and Recovery
- Regular database backups
- S3 bucket replication
- Disaster recovery procedures
- Data retention policies

---

This documentation provides a comprehensive overview of the medical report generation system. For specific implementation details, refer to the individual component documentation and code comments.

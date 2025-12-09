# CaseTracker Pro - Team Onboarding Guide

## Table of Contents
1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Architecture Overview](#architecture-overview)
4. [Core Features](#core-features)
5. [Development Setup](#development-setup)
6. [Authentication & Security](#authentication--security)
7. [API Integration](#api-integration)
8. [Page-by-Page Guide](#page-by-page-guide)
9. [Deployment](#deployment)
10. [Best Practices](#best-practices)

---

## Project Overview

**CaseTracker Pro** is a medical report generation system designed to streamline the creation of comprehensive medical reports through AI-powered analysis. The system serves as a bridge between case data and AI processing, providing an intuitive interface for medical professionals to generate, review, and manage case reports.

### Key Business Value
- **Automated Report Generation**: Reduces manual report creation time from hours to minutes
- **AI-Powered Analysis**: Leverages advanced AI models for comprehensive medical document analysis
- **Centralized Case Management**: Single platform for all case-related documents and reports
- **Version Control**: Track changes and compare different versions of Life Care Plans (LCPs)

---

## Technology Stack

### Frontend Framework: Streamlit
**Why Streamlit?**
- **Rapid Prototyping**: Enables fast development with minimal code
- **Python-Native**: Perfect fit for data science and AI applications
- **Built-in Components**: Rich UI components without complex frontend setup
- **Easy Deployment**: Simple deployment options including Render, Streamlit Cloud
- **Real-time Updates**: Automatic UI updates based on data changes

**Version**: 1.28.1 (stable, production-ready)

### Backend Framework: FastAPI
**Why FastAPI?**
- **High Performance**: Built on Starlette for async performance
- **Automatic Documentation**: OpenAPI/Swagger docs generated automatically
- **Type Safety**: Full Python type hints support
- **Modern Python**: Leverages async/await for concurrent operations
- **Easy Testing**: Built-in testing support with pytest

**Version**: 0.104.1

### Database: SQLite
**Why SQLite?**
- **Zero Configuration**: No separate database server needed
- **Portable**: Single file database, easy backup and migration
- **Sufficient Scale**: Perfect for current user load and data volume
- **ACID Compliant**: Full transaction support
- **Python Integration**: Excellent Python library support

### Cloud Storage: AWS S3
**Why AWS S3?**
- **Scalability**: Virtually unlimited storage capacity
- **Durability**: 99.999999999% durability guarantee
- **Security**: Fine-grained access controls with IAM
- **Integration**: Excellent Python SDK (boto3) support
- **Cost Effective**: Pay-as-you-go pricing model

### Authentication: Custom Implementation
**Why Custom Auth?**
- **Simple Requirements**: No need for complex OAuth flows initially
- **Full Control**: Complete control over user data and authentication logic
- **Flexibility**: Easy to extend with role-based access later
- **Privacy**: No third-party authentication services

---

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │    │    FastAPI      │    │     AWS S3     │
│   Frontend      │◄──►│    Backend      │◄──►│   Storage       │
│   (Port 8501)   │    │   (Port 8000)   │    │   (Documents)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   User Session  │    │   SQLite DB      │    │   N8n Workflow  │
│   Management    │    │  (reports.db)    │    │   (AI Processing)│
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Components

1. **Frontend (Streamlit Pages)**
   - `main.py` - Landing page and navigation hub
   - `pages/01_Case_Report.py` - Case report generation
   - `pages/02_Deposition.py` - Document viewer
   - `pages/04_Results.py` - Results display and download
   - `pages/05_History.py` - Case history and tracking
   - `pages/06_Version_Comparison.py` - LCP version comparison

2. **Backend (FastAPI)**
   - `backend/main.py` - Main API server
   - `backend/n8n_integration.py` - N8n workflow integration
   - SQLite database for metadata storage

3. **Supporting Modules**
   - `app/auth.py` - Authentication system
   - `app/ui.py` - UI components and styling
   - `app/s3_utils.py` - S3 integration utilities
   - `app/version_comparison.py` - Document comparison logic

---

## Core Features

### 1. Case Report Generation
**Purpose**: Generate comprehensive medical reports using AI analysis
**Workflow**:
1. User enters 4-digit Case ID
2. System validates case exists in S3
3. Triggers N8n workflow for AI processing
4. Tracks progress (typically 2 hours)
5. Notifies user when complete

**Key Features**:
- Real-time progress tracking
- Backend pinger to prevent timeouts
- Error handling and retry logic
- Debug mode for testing (Case ID: 0000)

### 2. Deposition Document Viewer
**Purpose**: Browse and view source documents for each case
**Features**:
- Document grouping by provider/source
- Built-in image viewer
- PDF and DOCX support
- Download capabilities
- Responsive design

**Technical Details**:
- Fetches documents from S3
- Groups by provider using filename patterns
- Caches results for performance

### 3. Results Dashboard
**Purpose**: View and download generated reports
**Features**:
- Real-time generation status
- Patient name extraction
- Report preview
- Download options (PDF, DOCX)
- Metrics and analytics

**Technical Highlights**:
- Progress tracking with session state
- Automatic refresh
- Error recovery
- File proxy for CORS issues

### 4. History Tracking
**Purpose**: Track all report generation history
**Features**:
- Complete case history
- Status tracking
- Search and filter
- Export capabilities
- Performance metrics

**Database Schema**:
```sql
CREATE TABLE reports (
    id INTEGER PRIMARY KEY,
    case_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    report_url TEXT,
    metadata TEXT
);
```

### 5. Version Comparison
**Purpose**: Compare different versions of LCP documents
**Features**:
- Side-by-side comparison
- Section-by-section analysis
- Change tracking
- Visual diff display
- Export comparison results

**Technical Implementation**:
- Advanced text comparison algorithms
- PDF parsing and analysis
- Visual diff generation
- S3 version management

---

## Development Setup

### Prerequisites
- Python 3.8+
- Git
- AWS Account (for S3)
- N8n instance (for AI workflows)

### Local Setup

1. **Clone Repository**
```bash
git clone <repository-url>
cd basic-streamlit-ui
```

2. **Install Dependencies**
```bash
pip install -r requirements.txt
```

3. **Environment Configuration**
```bash
# Copy example configuration
cp .env.example .env
# Edit .env with your settings
```

4. **Start Backend Server**
```bash
cd backend
python main.py
# Backend runs on http://localhost:8000
```

5. **Start Frontend**
```bash
# In main directory
streamlit run main.py
# Frontend runs on http://localhost:8501
```

### Environment Variables

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket_name

# Backend Configuration
BACKEND_BASE=http://localhost:8000

# N8n Configuration
N8N_WEBHOOK_URL=your_n8n_webhook_url
N8N_AUTH_TOKEN=your_n8n_token
```

---

## Authentication & Security

### Current Implementation
- **Simple Username/Password**: Basic authentication using bcrypt
- **Session Management**: Streamlit session state
- **Role-Based Access**: Admin and user roles
- **Password Hashing**: bcrypt for secure password storage

### User Management
Users are defined in `config.yaml`:
```yaml
credentials:
  usernames:
    user_name:
      email: user@example.com
      name: Display Name
      password: $2b$12$hashed_password
```

### Security Best Practices
1. **Password Security**: All passwords are bcrypt hashed
2. **Session Timeout**: Sessions expire after inactivity
3. **Input Validation**: All user inputs are validated
4. **CORS Protection**: Backend configured for specific origins
5. **S3 Security**: IAM roles with least privilege

### Future Enhancements
- OAuth 2.0 integration
- Multi-factor authentication
- Role-based permissions
- Audit logging
- Session encryption

---

## API Integration

### Backend API Endpoints

#### Core Endpoints
- `GET /health` - Health check
- `GET /s3/cases` - List available cases
- `GET /s3/case/{case_id}/report` - Get case report
- `POST /generate/{case_id}` - Start report generation

#### Document Endpoints
- `GET /proxy/docx` - Proxy DOCX files (CORS)
- `GET /docx/extract-text` - Extract text from DOCX
- `GET /s3/documents/{case_id}` - List case documents

#### Database Endpoints
- `GET /reports` - Get all reports
- `GET /reports/{case_id}` - Get specific report
- `POST /reports` - Create report entry
- `PUT /reports/{id}` - Update report status

### N8n Integration
The system integrates with N8n for AI processing workflows:

```python
# Workflow trigger
POST /n8n/webhook/generate-report
{
    "case_id": "1234",
    "user_email": "user@example.com",
    "timestamp": "2024-01-01T12:00:00Z"
}
```

**Workflow Steps**:
1. Receive case ID
2. Fetch documents from S3
3. Process with AI models
4. Generate report
5. Store results
6. Notify completion

---

## Page-by-Page Guide

### Main Dashboard (`main.py`)
**Purpose**: Central navigation hub
**Key Features**:
- User authentication check
- Navigation buttons to all pages
- Feature overview cards
- Quick start guide
- User profile display

**Code Structure**:
```python
def main():
    # Authentication check
    if not is_authenticated():
        show_login_page()
        return
    
    # Page configuration
    st.set_page_config(...)
    
    # UI rendering
    show_header(...)
    navigation_buttons()
    feature_cards()
    quick_start_guide()
```

### Case Report Generation (`pages/01_Case_Report.py`)
**Purpose**: Generate new medical reports
**Key Features**:
- Case ID validation
- Progress tracking
- Backend pinger
- Error handling
- Debug mode

**Workflow**:
1. User enters Case ID
2. System validates against S3
3. Triggers N8n workflow
4. Shows progress bar
5. Redirects to Results page

**Key Functions**:
- `_validate_case_id_exists()` - Check case in S3
- `_start_backend_pinger()` - Keep backend alive
- `_trigger_report_generation()` - Start AI workflow

### Deposition Viewer (`pages/02_Deposition.py`)
**Purpose**: View source documents
**Key Features**:
- Document listing
- Provider grouping
- Image viewer
- Download options
- Responsive layout

**Technical Implementation**:
```python
def group_documents_by_provider(documents):
    """Group documents by provider using filename patterns"""
    grouped = {}
    for doc in documents:
        provider = extract_provider_from_filename(doc['filename'])
        if provider not in grouped:
            grouped[provider] = []
        grouped[provider].append(doc)
    return grouped
```

### Results Dashboard (`pages/04_Results.py`)
**Purpose**: Display generated reports
**Key Features**:
- Real-time status updates
- Report preview
- Download options
- Patient information
- Progress metrics

**State Management**:
```python
# Session state tracking
st.session_state.generation_complete = False
st.session_state.generation_progress = 0
st.session_state.generation_start = datetime.now()
```

### History Page (`pages/05_History.py`)
**Purpose**: Track all report history
**Key Features**:
- Complete case listing
- Status tracking
- Search functionality
- Export options
- Performance metrics

**Database Operations**:
```python
def get_report_history():
    """Fetch all reports from database"""
    conn = get_conn()
    cursor = conn.execute("SELECT * FROM reports ORDER BY created_at DESC")
    return cursor.fetchall()
```

### Version Comparison (`pages/06_Version_Comparison.py`)
**Purpose**: Compare LCP document versions
**Key Features**:
- Side-by-side comparison
- Section analysis
- Change tracking
- Visual diffs
- Export results

**Comparison Logic**:
```python
class LCPVersionComparator:
    def compare_versions(self, case_id, version1, version2):
        """Compare two versions of LCP documents"""
        v1_content = self.fetch_version(case_id, version1)
        v2_content = self.fetch_version(case_id, version2)
        return self.generate_diff(v1_content, v2_content)
```

---

## Deployment

### Render Deployment
The application is deployed on Render using the following configuration:

**render.yaml**:
```yaml
services:
  - type: web
    name: case-tracker-pro
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: streamlit run main.py --server.port $PORT
    envVars:
      - key: PORT
        value: 10000
```

### Deployment Steps
1. **Connect Repository**: Link GitHub repository to Render
2. **Configure Environment**: Set environment variables
3. **Deploy**: Automatic deployment on push
4. **Monitor**: Check logs and health status

### Production Considerations
- **SSL/TLS**: Automatic SSL certificates
- **Scaling**: Horizontal scaling with load balancers
- **Monitoring**: Application performance monitoring
- **Backups**: Regular database and file backups
- **Security**: WAF, DDoS protection

---

## Best Practices

### Code Organization
- **Modular Structure**: Separate concerns into modules
- **Consistent Naming**: Use clear, descriptive names
- **Type Hints**: Use Python type hints throughout
- **Documentation**: Document all functions and classes
- **Error Handling**: Comprehensive error handling

### Performance Optimization
- **Caching**: Use Streamlit caching for expensive operations
- **Lazy Loading**: Load data only when needed
- **Async Operations**: Use async for I/O operations
- **Database Indexing**: Proper database indexes
- **Image Optimization**: Compress and optimize images

### Security Practices
- **Input Validation**: Validate all user inputs
- **SQL Injection**: Use parameterized queries
- **XSS Protection**: Sanitize user-generated content
- **Authentication**: Strong password policies
- **Environment Variables**: Never hardcode secrets

### Testing Strategy
- **Unit Tests**: Test individual functions
- **Integration Tests**: Test API endpoints
- **End-to-End Tests**: Test complete workflows
- **Performance Tests**: Load testing
- **Security Tests**: Vulnerability scanning

### Development Workflow
1. **Feature Branches**: Create branches for new features
2. **Code Review**: Peer review for all changes
3. **Testing**: Comprehensive testing before merge
4. **Documentation**: Update docs with changes
5. **Deployment**: Staged deployment process

---

## Troubleshooting Guide

### Common Issues

#### Backend Connection Issues
**Problem**: Frontend can't connect to backend
**Solution**:
1. Check backend is running on port 8000
2. Verify BACKEND_BASE environment variable
3. Check CORS configuration
4. Review firewall settings

#### S3 Connection Issues
**Problem**: Can't access S3 resources
**Solution**:
1. Verify AWS credentials
2. Check bucket permissions
3. Verify region configuration
4. Test IAM policies

#### Authentication Issues
**Problem**: Users can't log in
**Solution**:
1. Check config.yaml format
2. Verify password hashes
3. Clear session state
4. Review auth.py logic

#### Report Generation Issues
**Problem**: Reports not generating
**Solution**:
1. Check N8n webhook URL
2. Verify case ID exists
3. Review backend logs
4. Check S3 document availability

### Debug Mode
Use Case ID "0000" for testing without real data:
```python
if str(case_id) == "0000":
    return {"exists": True, "message": "Debug mode"}
```

### Log Analysis
Check application logs for errors:
```bash
# Backend logs
cd backend && python main.py

# Frontend logs
streamlit run main.py --logger.level debug
```

---

## Future Roadmap

### Planned Enhancements
1. **Advanced Authentication**: OAuth 2.0, SSO
2. **Enhanced UI**: Modern design system
3. **Mobile Support**: Responsive mobile interface
4. **Advanced Analytics**: Detailed usage metrics
5. **API Versioning**: Versioned API endpoints
6. **Performance**: Caching layer, CDN integration

### Technology Upgrades
- **Database**: PostgreSQL for production scaling
- **Frontend**: React/Next.js for advanced UI
- **Authentication**: Auth0 or Firebase Auth
- **Monitoring**: DataDog, New Relic
- **CI/CD**: GitHub Actions, automated testing

---

## Contact & Support

### Development Team
- **Lead Developer**: [Contact Info]
- **Backend Specialist**: [Contact Info]
- **UI/UX Designer**: [Contact Info]
- **DevOps Engineer**: [Contact Info]

### Support Channels
- **Documentation**: This guide and code comments
- **Issue Tracking**: GitHub Issues
- **Communication**: Slack/Teams channel
- **Emergency**: Contact lead developer directly

---

*Last Updated: January 2025*
*Version: 1.0.0*

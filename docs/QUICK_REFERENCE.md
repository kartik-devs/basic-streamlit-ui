# CaseTracker Pro - Quick Reference Guide

## Technology Stack Summary
- **Frontend**: Streamlit 1.28.1 (Python web framework)
- **Backend**: FastAPI 0.104.1 (Python API framework)  
- **Database**: SQLite (reports.db)
- **Storage**: AWS S3 (documents and reports)
- **Authentication**: Custom bcrypt-based system
- **Deployment**: Render (cloud platform)

## Key Files & Directories
```
├── main.py                 # Main dashboard and navigation
├── pages/
│   ├── 01_Case_Report.py   # Report generation
│   ├── 02_Deposition.py    # Document viewer  
│   ├── 04_Results.py       # Results display
│   ├── 05_History.py       # Case history
│   └── 06_Version_Comparison.py # LCP comparison
├── app/
│   ├── auth.py             # Authentication logic
│   ├── ui.py               # UI components & styling
│   ├── s3_utils.py         # S3 integration
│   └── version_comparison.py # Document comparison
├── backend/
│   ├── main.py             # FastAPI server
│   └── n8n_integration.py  # AI workflow integration
├── config.yaml             # User credentials
└── requirements.txt        # Python dependencies
```

## Common Commands

### Development Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Start backend (port 8000)
cd backend && python main.py

# Start frontend (port 8501)  
streamlit run main.py
```

### Testing
```bash
# Test backend health
curl http://localhost:8000/health

# Test S3 connection
curl http://localhost:8000/s3/cases

# Debug mode - use case ID "0000"
```

## Core Features by Page

### 🏠 Main Dashboard (`main.py`)
- **Purpose**: Central navigation hub
- **Key Functions**: Authentication check, navigation buttons, feature overview
- **User Flow**: Login → Dashboard → Select page

### 📋 Case Report (`pages/01_Case_Report.py`)
- **Purpose**: Generate AI-powered medical reports
- **Workflow**: Enter Case ID → Validate → Trigger N8n → Track progress
- **Key Features**: Real-time progress, backend pinger, debug mode (0000)
- **Processing Time**: ~2 hours per report

### 📄 Deposition (`pages/02_Deposition.py`)
- **Purpose**: View source documents
- **Features**: Document grouping, image viewer, downloads
- **Grouping Logic**: Groups by provider using filename patterns

### 📊 Results (`pages/04_Results.py`)
- **Purpose**: Display generated reports
- **Features**: Real-time status, report preview, download options
- **State Management**: Uses session state for progress tracking

### 📚 History (`pages/05_History.py`)
- **Purpose**: Track all report generation history
- **Features**: Complete case listing, search, export, metrics
- **Database**: SQLite with reports table

### 🔄 Version Comparison (`pages/06_Version_Comparison.py`)
- **Purpose**: Compare different LCP document versions
- **Features**: Side-by-side comparison, section analysis, visual diffs

## API Endpoints

### Core Backend Endpoints
```python
GET  /health                    # Health check
GET  /s3/cases                  # List available cases
GET  /s3/case/{case_id}/report  # Get case report
POST /generate/{case_id}        # Start report generation
GET  /reports                   # Get all reports
```

### Document Endpoints
```python
GET  /proxy/docx                # Proxy DOCX files (CORS)
GET  /docx/extract-text         # Extract text from DOCX
GET  /s3/documents/{case_id}   # List case documents
```

## Authentication

### User Management
- **Config File**: `config.yaml`
- **Password Hashing**: bcrypt
- **Session Management**: Streamlit session state
- **Roles**: Admin, User

### Default Users
```yaml
credentials:
  usernames:
    admin:
      email: admin@casetracker.com
      name: Admin User
      password: [bcrypt_hash]
```

## Environment Variables

```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_bucket

# Backend Configuration  
BACKEND_BASE=http://localhost:8000

# N8n Integration
N8N_WEBHOOK_URL=your_webhook_url
N8N_AUTH_TOKEN=your_token
```

## Database Schema

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

## Common Issues & Solutions

### Backend Connection
- **Issue**: Frontend can't connect to backend
- **Solution**: Check backend running on port 8000, verify BACKEND_BASE

### S3 Access
- **Issue**: Can't access S3 resources  
- **Solution**: Verify AWS credentials and bucket permissions

### Authentication
- **Issue**: Users can't log in
- **Solution**: Check config.yaml format and password hashes

### Report Generation
- **Issue**: Reports not generating
- **Solution**: Check N8n webhook, verify case ID exists

## Debug Mode
Use Case ID **"0000"** for testing without real data:
```python
if str(case_id) == "0000":
    return {"exists": True, "message": "Debug mode"}
```

## Performance Tips
- Use Streamlit caching for expensive operations
- Implement lazy loading for large datasets
- Use async operations for I/O
- Add database indexes for common queries
- Optimize images and documents

## Security Best Practices
- Validate all user inputs
- Use parameterized SQL queries
- Sanitize user-generated content
- Never hardcode secrets
- Use environment variables for configuration

## Deployment
- **Platform**: Render
- **SSL**: Automatic certificates
- **Scaling**: Horizontal scaling available
- **Monitoring**: Built-in health checks
- **Backups**: Regular database backups

## Development Workflow
1. Create feature branch
2. Make changes with tests
3. Code review
4. Merge to main
5. Auto-deploy to staging
6. Manual promotion to production

## Support
- **Documentation**: Full guide in `docs/TEAM_ONBOARDING_GUIDE.md`
- **Issues**: GitHub Issues
- **Emergency**: Contact lead developer
- **Logs**: Check backend and frontend logs for errors

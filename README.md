# Medical Report Generation System

A comprehensive system for generating medical reports for legal cases using n8n workflows, AI models, and a modern web interface.

## 🏥 Overview

This system helps doctors and patients involved in legal cases (accidents, medical malpractice, etc.) by automatically generating comprehensive medical reports from patient data stored in S3. The system processes data through multiple AI-powered sections and outputs an HTML report that can be converted to PDF.

## 🏗️ Architecture

- **Frontend**: Streamlit web application with authentication
- **Backend**: FastAPI REST API
- **Workflows**: n8n automation workflows
- **Storage**: S3 for documents, SQLite for metadata
- **AI Models**: Google Gemini and Vertex AI

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- n8n instance running
- S3 bucket configured
- Google Cloud credentials (for AI models)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd OCR
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   # Copy and edit the configuration
   cp config/n8n_config.yaml config/n8n_config_local.yaml
   ```

4. **Set up environment variables**
   ```bash
   export N8N_BASE_URL="http://localhost:5678"
   export N8N_API_KEY="your_api_key"
   export BACKEND_BASE="http://localhost:8000"
   export ARTIFACTS_DIR="./artifacts"
   ```

5. **Start the backend server**
   ```bash
   cd backend
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

6. **Start the frontend**
   ```bash
   streamlit run main.py
   ```

## 📋 Usage

### 1. Authentication
- Access the web application at `http://localhost:8501`
- Register a new account or sign in with existing credentials

### 2. Generate Report
- Navigate to "Case Report" page
- Enter a 4-digit Case ID (Patient ID)
- Click "Generate Report"

### 3. Monitor Progress
- The system will show real-time progress of all workflow steps:
  - OCR Text Extraction
  - Sections 1-8 processing
  - Final report generation

### 4. Download Report
- Once complete, download the generated PDF report
- View accuracy metrics and processing time

## 🔧 Configuration

### n8n Workflows

The system expects the following n8n workflows to be configured:

1. **OCR Text Extraction**: `/webhook/ocr-text-extraction`
2. **Section Workflows**: `/webhook/section-{1-8}`
3. **Complete Report**: `/webhook/complete-report-generation`

### External Services

Configure the following external services in `config/n8n_config.yaml`:

- OCR Service: `http://54.198.187.195:80`
- Section 2 Service: `http://98.82.36.138:80`
- Section 4 Service: `http://54.198.187.195:80`
- Accuracy Service: `http://3.92.236.248:80`

### AI Models

- **Google Gemini**: For Sections 1 and 3
- **Google Vertex AI**: For Section 4 (dual agents)

## 📊 API Endpoints

### Report Generation
```http
POST /n8n/generate-report
Parameters: patient_id, username
```

### Status Checking
```http
GET /n8n/report-status/{report_id}
```

### Workflow Status
```http
GET /n8n/workflow-status/{execution_id}
```

### Report Download
```http
GET /n8n/download-report/{report_id}
```

## 🔍 Workflow Steps

### 1. OCR Text Extraction
- Retrieves patient documents from S3
- Classifies pages (Printed, Handwritten, Scanned)
- Extracts text using OCR technology
- Stores classification results

### 2. Section Processing (1-8)
- **Section 1**: Table of contents and initial content (Gemini)
- **Section 2**: Content generation with accuracy metrics
- **Section 3**: Patient intake data from Zoho/Snowflake (Gemini)
- **Section 4**: Dual AI agent processing (Vertex AI)
- **Sections 5-7**: Sequential content creation
- **Section 8**: Gender-based processing

### 3. Final Assembly
- Combines all section outputs
- Applies final formatting
- Calculates accuracy metrics
- Generates HTML/PDF report

## 🛠️ Development

### Project Structure
```
├── main.py                 # Streamlit main application
├── backend/                # FastAPI backend
│   ├── main.py            # API endpoints
│   └── n8n_integration.py # n8n workflow integration
├── pages/                  # Streamlit pages
│   ├── 01_Case_Report.py  # Case input page
│   ├── 02_Generating_Report.py # Progress tracking
│   └── 03_Results.py      # Results display
├── app/                    # Application modules
│   ├── ui.py              # UI components
│   └── auth.py            # Authentication
├── config/                 # Configuration files
│   └── n8n_config.yaml    # n8n integration config
└── artifacts/              # Generated reports
```

### Adding New Workflows

1. **Create n8n workflow** with appropriate webhook endpoint
2. **Add webhook URL** to `config/n8n_config.yaml`
3. **Update integration** in `backend/n8n_integration.py`
4. **Test workflow** using the web interface

### Testing

```bash
# Test backend API
curl -X GET "http://localhost:8000/health"

# Test n8n webhook
curl -X POST "http://localhost:5678/webhook/ocr-text-extraction" \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "1234"}'
```

## 🔒 Security

### Authentication
- User authentication required for all operations
- Session-based authentication with Streamlit
- API key authentication for n8n integration

### Data Privacy
- Patient data encrypted in transit and at rest
- S3 bucket access controls
- Audit logging for all operations
- HIPAA compliance considerations

## 📈 Monitoring

### Health Checks
- n8n workflow availability
- Backend API responsiveness
- Database connectivity
- S3 bucket access

### Logging
- Structured logging for all operations
- Error tracking and alerting
- Performance metrics collection
- User activity logging

## 🚨 Troubleshooting

### Common Issues

1. **n8n Connection Failed**
   ```bash
   # Check n8n status
   curl -X GET "http://localhost:5678/api/v1/health"
   ```

2. **Workflow Timeout**
   - Increase timeout values in configuration
   - Check n8n workflow performance
   - Monitor resource usage

3. **Report Generation Failed**
   - Check S3 bucket permissions
   - Verify patient data exists
   - Review workflow logs

### Debug Mode

Enable debug mode in `config/n8n_config.yaml`:
```yaml
development:
  debug: true
  mock_responses: true
```

## 📚 Documentation

- [Workflow Documentation](WORKFLOW_DOCUMENTATION.md)
- [API Reference](docs/api.md)
- [Deployment Guide](docs/deployment.md)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the documentation

---

**Note**: This system is designed for medical report generation and should be used in compliance with relevant healthcare regulations and data privacy laws.

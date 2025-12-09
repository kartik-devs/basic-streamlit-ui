# CaseTracker Pro - Architecture Documentation

## System Architecture Overview

```mermaid
graph TB
    subgraph "Frontend Layer"
        A[Streamlit App<br/>Port 8501]
        A1[Main Dashboard]
        A2[Case Report Page]
        A3[Deposition Viewer]
        A4[Results Dashboard]
        A5[History Page]
        A6[Version Comparison]
        
        A --> A1
        A --> A2
        A --> A3
        A --> A4
        A --> A5
        A --> A6
    end
    
    subgraph "API Gateway"
        B[FastAPI Server<br/>Port 8000]
        B1[Authentication]
        B2[CORS Middleware]
        B3[Request Routing]
        B4[Error Handling]
        
        B --> B1
        B --> B2
        B --> B3
        B --> B4
    end
    
    subgraph "Business Logic"
        C[Report Generator]
        C1[Case Validation]
        C2[Document Processing]
        C3[Progress Tracking]
        C4[Version Comparison]
        
        C --> C1
        C --> C2
        C --> C3
        C --> C4
    end
    
    subgraph "Data Layer"
        D[SQLite Database]
        D1[Reports Table]
        D2[Users Table]
        D3[Sessions Table]
        
        D --> D1
        D --> D2
        D --> D3
    end
    
    subgraph "Storage Layer"
        E[AWS S3]
        E1[Source Documents]
        E2[Generated Reports]
        E3[Version History]
        
        E --> E1
        E --> E2
        E --> E3
    end
    
    subgraph "External Services"
        F[N8n Workflow]
        F1[AI Processing]
        F2[Document Analysis]
        F3[Report Generation]
        
        F --> F1
        F --> F2
        F --> F3
    end
    
    A -.->|HTTP API| B
    B --> C
    C --> D
    C --> E
    C -.->|Webhook| F
    F -.->|Callback| B
```

## Data Flow Architecture

```mermaid
sequenceDiagram
    participant U as User
    participant F as Frontend
    participant A as API Gateway
    participant DB as Database
    participant S3 as AWS S3
    participant N8n as N8n Workflow
    
    Note over U,N8n: Case Report Generation Flow
    
    U->>F: Enter Case ID
    F->>A: POST /generate/{case_id}
    A->>DB: Create report entry
    A->>S3: Validate case exists
    S3-->>A: Case validation result
    A->>N8n: Trigger workflow
    N8n-->>A: Workflow started
    A-->>F: Generation started
    F-->>U: Show progress tracking
    
    Note over U,N8n: Progress Tracking
    
    F->>A: GET /reports/{case_id}
    A->>DB: Check status
    DB-->>A: Current status
    A-->>F: Status update
    F-->>U: Update progress bar
    
    Note over U,N8n: Report Completion
    
    N8n->>S3: Store generated report
    N8n->>A: POST /webhook/completion
    A->>DB: Update status to complete
    A-->>F: Notification
    F-->>U: Report ready
```

## Component Architecture

### Frontend Components

```mermaid
graph LR
    subgraph "Streamlit Pages"
        A[main.py<br/>Navigation Hub]
        B[01_Case_Report.py<br/>Report Generation]
        C[02_Deposition.py<br/>Document Viewer]
        D[04_Results.py<br/>Results Display]
        E[05_History.py<br/>History Tracking]
        F[06_Version_Comparison.py<br/>Version Diff]
    end
    
    subgraph "Shared Components"
        G[app/auth.py<br/>Authentication]
        H[app/ui.py<br/>UI Components]
        I[app/s3_utils.py<br/>S3 Integration]
        J[app/version_comparison.py<br/>Comparison Logic]
    end
    
    A --> G
    A --> H
    B --> G
    B --> H
    B --> I
    C --> G
    C --> H
    C --> I
    D --> G
    D --> H
    D --> I
    E --> G
    E --> H
    F --> G
    F --> H
    F --> I
    F --> J
```

### Backend Components

```mermaid
graph TB
    subgraph "FastAPI Application"
        A[main.py<br/>API Server]
        B[n8n_integration.py<br/>Workflow Integration]
    end
    
    subgraph "API Endpoints"
        C[Health Check]
        D[Authentication]
        E[S3 Operations]
        F[Report Generation]
        G[Database Operations]
        H[Document Proxy]
    end
    
    subgraph "Middleware"
        I[CORS Handler]
        J[Error Handler]
        K[Request Logger]
    end
    
    A --> B
    A --> C
    A --> D
    A --> E
    A --> F
    A --> G
    A --> H
    A --> I
    A --> J
    A --> K
```

## Database Schema

```mermaid
erDiagram
    REPORTS {
        int id PK
        text case_id FK
        text status
        timestamp created_at
        timestamp completed_at
        text report_url
        text metadata
        text user_email
    }
    
    USERS {
        text email PK
        text name
        text password_hash
        text role
        timestamp created_at
        timestamp last_login
    }
    
    SESSIONS {
        text session_id PK
        text user_email FK
        timestamp created_at
        timestamp expires_at
        text session_data
    }
    
    CASE_DOCUMENTS {
        int id PK
        text case_id FK
        text filename
        text s3_key
        text provider
        timestamp uploaded_at
        text document_type
    }
    
    REPORTS ||--o{ CASE_DOCUMENTS : has
    USERS ||--o{ REPORTS : creates
    USERS ||--o{ SESSIONS : has
```

## Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        A[Network Security<br/>SSL/TLS, CORS]
        B[Authentication<br/>bcrypt, Session Management]
        C[Authorization<br/>Role-Based Access]
        D[Data Protection<br/>Encryption at Rest]
        E[API Security<br/>Input Validation, Rate Limiting]
    end
    
    subgraph "AWS Security"
        F[IAM Roles<br/>Least Privilege]
        G[S3 Policies<br/>Bucket Policies]
        H[VPC Configuration<br/>Network Isolation]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        subgraph "Render Platform"
            A[Load Balancer]
            B[Streamlit Frontend<br/>Port 10000]
            C[FastAPI Backend<br/>Port 8000]
        end
        
        subgraph "AWS Infrastructure"
            D[S3 Bucket<br/>us-east-1]
            E[IAM Roles]
            F[CloudFront<br/>CDN]
        end
        
        subgraph "External Services"
            G[N8n Instance<br/>AI Workflows]
            H[Monitoring<br/>Logs & Alerts]
        end
    end
    
    A --> B
    A --> C
    B --> D
    C --> D
    D --> E
    D --> F
    C --> G
    B --> H
    C --> H
```

## Technology Stack Details

### Frontend Stack
- **Streamlit 1.28.1**: Python web framework for data apps
- **Streamlit Extras 0.3.5**: Additional UI components
- **Python 3.8+**: Runtime environment
- **HTML/CSS**: Custom styling and layout

### Backend Stack
- **FastAPI 0.104.1**: Modern Python web framework
- **Uvicorn 0.24.0**: ASGI server
- **SQLite 3**: Embedded database
- **Boto3 1.34.0**: AWS SDK

### Infrastructure Stack
- **AWS S3**: Object storage
- **AWS IAM**: Identity and access management
- **Render**: PaaS for deployment
- **N8n**: Workflow automation
- **GitHub**: Version control and CI/CD

## Performance Architecture

```mermaid
graph TB
    subgraph "Performance Optimizations"
        A[Frontend Caching<br/>Streamlit @st.cache_data]
        B[Backend Caching<br/>In-memory response cache]
        C[Database Optimization<br/>Indexes, Query Optimization]
        D[CDN Integration<br/>CloudFront for static assets]
        E[Async Processing<br/>Background tasks, Webhooks]
    end
    
    subgraph "Monitoring"
        F[Health Checks<br/>/health endpoint]
        G[Performance Metrics<br/>Response times, Error rates]
        H[Resource Monitoring<br/>CPU, Memory, Storage]
    end
    
    A --> F
    B --> G
    C --> H
    D --> F
    E --> G
```

## Scaling Architecture

### Horizontal Scaling Strategy
```mermaid
graph LR
    subgraph "Current Scale"
        A[Single Instance<br/>~100 users]
    end
    
    subgraph "Scale to 1000 Users"
        B[Load Balancer]
        C[Multiple Frontend Instances]
        D[Backend API Cluster]
        E[Read Replicas]
    end
    
    subgraph "Scale to 10000 Users"
        F[Application Load Balancer]
        G[Auto-scaling Frontend]
        H[Microservices Architecture]
        I[PostgreSQL Cluster]
        J[Redis Cache Layer]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    H --> I
    I --> J
```

## Integration Architecture

### Third-Party Integrations
```mermaid
graph TB
    subgraph "Core Integrations"
        A[AWS S3<br/>Document Storage]
        B[N8n<br/>AI Workflows]
        C[Render<br/>Hosting Platform]
    end
    
    subgraph "Future Integrations"
        D[OAuth Providers<br/>Google, Microsoft]
        E[Payment Processors<br/>Stripe, PayPal]
        F[Analytics<br/>Google Analytics, Mixpanel]
        G[Communication<br/>SendGrid, Twilio]
    end
    
    A --> D
    B --> E
    C --> F
    D --> G
```

## Data Architecture

### Data Flow Patterns
```mermaid
graph LR
    subgraph "Input Data"
        A[User Input<br/>Case IDs, Preferences]
        B[Document Upload<br/>PDFs, DOCX, Images]
    end
    
    subgraph "Processing"
        C[Validation<br/>Format, Size, Type]
        D[AI Processing<br/>N8n Workflows]
        E[Report Generation<br/>Document Creation]
    end
    
    subgraph "Output Data"
        F[Generated Reports<br/>PDF, DOCX]
        G[Analytics<br/>Usage Metrics]
        H[History<br/>Audit Trail]
    end
    
    A --> C
    B --> C
    C --> D
    D --> E
    E --> F
    E --> G
    E --> H
```

## Monitoring & Observability

```mermaid
graph TB
    subgraph "Monitoring Stack"
        A[Application Metrics<br/>Response times, Error rates]
        B[Infrastructure Metrics<br/>CPU, Memory, Disk]
        C[Business Metrics<br/>Report generation success]
        D[User Analytics<br/>Page views, Feature usage]
    end
    
    subgraph "Alerting"
        E[Health Check Failures]
        F[Performance Degradation]
        G[Security Events]
        H[Business Rule Violations]
    end
    
    A --> E
    B --> F
    C --> G
    D --> H
```

## Development Architecture

### Code Organization
```
basic-streamlit-ui/
├── 📁 frontend/
│   ├── 📄 main.py                 # Entry point
│   ├── 📁 pages/                  # Streamlit pages
│   └── 📁 app/                    # Shared components
├── 📁 backend/
│   ├── 📄 main.py                 # API server
│   └── 📄 n8n_integration.py      # External integrations
├── 📁 docs/                       # Documentation
├── 📁 config/                     # Configuration files
├── 📄 requirements.txt            # Dependencies
└── 📄 deploy/                     # Deployment scripts
```

### Development Workflow
```mermaid
graph LR
    A[Local Development<br/>Docker Compose]
    B[Feature Branch<br/>Git Flow]
    C[Code Review<br/>Pull Requests]
    D[Testing<br/>Unit, Integration, E2E]
    E[Staging<br/>Preview Deployments]
    F[Production<br/>Blue-Green Deploy]
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

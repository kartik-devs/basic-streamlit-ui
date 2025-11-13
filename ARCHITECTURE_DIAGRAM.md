# LCP Version Comparison - Architecture Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                              │
│                    (Streamlit Web Application)                      │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ User Actions
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    PRESENTATION LAYER                               │
│              pages/06_Version_Comparison.py                         │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │
│  │ Case Input   │  │ Version List │  │ Report View  │            │
│  │ Component    │  │ Component    │  │ Component    │            │
│  └──────────────┘  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ Function Calls
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                             │
│              app/version_comparison.py                              │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │           LCPVersionComparator Class                       │   │
│  │                                                            │   │
│  │  ┌──────────────────┐  ┌──────────────────┐             │   │
│  │  │ get_lcp_versions │  │ extract_text     │             │   │
│  │  └──────────────────┘  └──────────────────┘             │   │
│  │                                                            │   │
│  │  ┌──────────────────┐  ┌──────────────────┐             │   │
│  │  │ extract_sections │  │ compare_texts    │             │   │
│  │  └──────────────────┘  └──────────────────┘             │   │
│  │                                                            │   │
│  │  ┌──────────────────┐  ┌──────────────────┐             │   │
│  │  │ compare_versions │  │ generate_report  │             │   │
│  │  └──────────────────┘  └──────────────────┘             │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ S3 Operations
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA ACCESS LAYER                                │
│                   app/s3_utils.py                                   │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │              S3Manager Class                               │   │
│  │                                                            │   │
│  │  ┌──────────────────┐  ┌──────────────────┐             │   │
│  │  │ list_objects_v2  │  │ download_file    │             │   │
│  │  └──────────────────┘  └──────────────────┘             │   │
│  │                                                            │   │
│  │  ┌──────────────────┐  ┌──────────────────┐             │   │
│  │  │ get_case_files   │  │ list_cases       │             │   │
│  │  └──────────────────┘  └──────────────────┘             │   │
│  └────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  │ AWS SDK (boto3)
                                  ↓
┌─────────────────────────────────────────────────────────────────────┐
│                         STORAGE LAYER                               │
│                      AWS S3 Bucket                                  │
│                   (finallcpreports)                                 │
│                                                                     │
│  case_3424/                                                         │
│  ├── Output/                                                        │
│  │   ├── 202411130900-3424-CompleteAIGeneratedReport.pdf          │
│  │   ├── 202411130930-3424-CompleteAIGeneratedReport.pdf          │
│  │   └── 202411131000-3424-CompleteAIGeneratedReport.pdf          │
│  └── GroundTruth/                                                   │
│      └── 3424_LCP_Patient_Name.pdf                                 │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagram

```
┌─────────┐
│  User   │
└────┬────┘
     │
     │ 1. Enter Case ID
     ↓
┌─────────────────┐
│  UI Component   │
└────┬────────────┘
     │
     │ 2. Request Versions
     ↓
┌─────────────────────────┐
│  LCPVersionComparator   │
└────┬────────────────────┘
     │
     │ 3. List S3 Objects
     ↓
┌─────────────┐
│  S3Manager  │
└────┬────────┘
     │
     │ 4. Query S3
     ↓
┌─────────┐
│   S3    │
└────┬────┘
     │
     │ 5. Return File List
     ↓
┌─────────────┐
│  S3Manager  │
└────┬────────┘
     │
     │ 6. Return Versions
     ↓
┌─────────────────────────┐
│  LCPVersionComparator   │
└────┬────────────────────┘
     │
     │ 7. Display Versions
     ↓
┌─────────────────┐
│  UI Component   │
└────┬────────────┘
     │
     │ 8. User Selects Versions
     ↓
┌─────────────────┐
│  UI Component   │
└────┬────────────┘
     │
     │ 9. Request Comparison
     ↓
┌─────────────────────────┐
│  LCPVersionComparator   │
└────┬────────────────────┘
     │
     │ 10. Download PDFs
     ↓
┌─────────────┐
│  S3Manager  │
└────┬────────┘
     │
     │ 11. Get PDF Bytes
     ↓
┌─────────┐
│   S3    │
└────┬────┘
     │
     │ 12. Return PDF Data
     ↓
┌─────────────────────────┐
│  LCPVersionComparator   │
│                         │
│  13. Extract Text       │
│  14. Parse Sections     │
│  15. Compare Texts      │
│  16. Generate Report    │
└────┬────────────────────┘
     │
     │ 17. Return Report
     ↓
┌─────────────────┐
│  UI Component   │
└────┬────────────┘
     │
     │ 18. Display Report
     ↓
┌─────────┐
│  User   │
└─────────┘
```

## Component Interaction Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                      Comparison Process                          │
└──────────────────────────────────────────────────────────────────┘

Step 1: Version Discovery
┌─────────────┐    list_objects_v2()    ┌─────────┐
│ Comparator  │ ──────────────────────→ │   S3    │
└─────────────┘                          └─────────┘
       ↓
       │ Filter by pattern:
       │ - *CompleteAIGenerated*.pdf
       │ - *LCP*.pdf
       ↓
┌─────────────┐
│ Version List│
└─────────────┘

Step 2: PDF Processing
┌─────────────┐    download_file()      ┌─────────┐
│ Comparator  │ ──────────────────────→ │   S3    │
└─────────────┘                          └─────────┘
       ↓
       │ PDF Bytes
       ↓
┌─────────────┐    extract_text()       ┌─────────┐
│ Comparator  │ ──────────────────────→ │ PyPDF2  │
└─────────────┘                          └─────────┘
       ↓
       │ Plain Text
       ↓
┌─────────────┐    extract_sections()
│ Comparator  │ ─────────────────────→ Section Dict
└─────────────┘

Step 3: Comparison
┌─────────────┐
│  Section 1  │ ──┐
└─────────────┘   │
                  │    compare_texts()    ┌──────────┐
┌─────────────┐   ├─────────────────────→ │ difflib  │
│  Section 1' │ ──┘                       └──────────┘
└─────────────┘                                 ↓
                                          ┌──────────┐
                                          │   Diff   │
                                          │  Result  │
                                          └──────────┘

Step 4: Report Generation
┌─────────────┐
│ Diff Results│
└──────┬──────┘
       │
       ├─────→ HTML Format ─────→ ┌──────────────┐
       │                          │  HTML Report │
       │                          └──────────────┘
       │
       └─────→ PDF Format ──────→ ┌──────────────┐
                                  │  PDF Report  │
                                  │ (ReportLab)  │
                                  └──────────────┘
```

## Comparison Algorithm Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Comparison Algorithm                     │
└─────────────────────────────────────────────────────────────┘

Input: Version A, Version B

┌──────────────┐
│  Version A   │
│   (PDF)      │
└──────┬───────┘
       │
       ↓ Extract Text
┌──────────────┐
│   Text A     │
└──────┬───────┘
       │
       ↓ Parse Sections
┌──────────────┐
│  Sections A  │
│  - Section 1 │
│  - Section 2 │
│  - Section 3 │
└──────┬───────┘
       │
       │                    ┌──────────────┐
       │                    │  Version B   │
       │                    │   (PDF)      │
       │                    └──────┬───────┘
       │                           │
       │                           ↓ Extract Text
       │                    ┌──────────────┐
       │                    │   Text B     │
       │                    └──────┬───────┘
       │                           │
       │                           ↓ Parse Sections
       │                    ┌──────────────┐
       │                    │  Sections B  │
       │                    │  - Section 1 │
       │                    │  - Section 2 │
       │                    │  - Section 4 │
       │                    └──────┬───────┘
       │                           │
       └───────────┬───────────────┘
                   │
                   ↓ Compare Section Names
            ┌──────────────┐
            │ Section Map  │
            │ 1: Both      │
            │ 2: Both      │
            │ 3: Only A    │
            │ 4: Only B    │
            └──────┬───────┘
                   │
                   ↓ For Each Section
            ┌──────────────┐
            │   difflib    │
            │   Compare    │
            └──────┬───────┘
                   │
                   ↓ Classify Changes
            ┌──────────────┐
            │   Results    │
            │ - Added      │
            │ - Removed    │
            │ - Modified   │
            │ - Unchanged  │
            └──────┬───────┘
                   │
                   ↓ Generate Report
            ┌──────────────┐
            │ Final Report │
            │  (HTML/PDF)  │
            └──────────────┘
```

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    External Dependencies                    │
└─────────────────────────────────────────────────────────────┘

streamlit (1.28.1)
    └─→ UI Framework

boto3 (1.34.0)
    └─→ AWS S3 Access

PyPDF2 (3.0.1)
    └─→ PDF Text Extraction (Primary)

pdfplumber (0.10.3)
    └─→ PDF Text Extraction (Fallback)

reportlab (4.0.7)
    └─→ PDF Report Generation

difflib (stdlib)
    └─→ Text Comparison

re (stdlib)
    └─→ Pattern Matching

io (stdlib)
    └─→ Byte Stream Handling

datetime (stdlib)
    └─→ Timestamp Handling
```

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Error Handling                           │
└─────────────────────────────────────────────────────────────┘

User Action
    ↓
Try: Execute Operation
    │
    ├─→ Success ─→ Return Result
    │
    └─→ Exception
         │
         ├─→ S3 Error
         │    ├─→ NoCredentialsError → Show config help
         │    ├─→ ClientError → Show S3 error message
         │    └─→ Timeout → Suggest retry
         │
         ├─→ PDF Error
         │    ├─→ ImportError → Show install instructions
         │    ├─→ Corrupt PDF → Show file error
         │    └─→ Extraction Failed → Try fallback method
         │
         ├─→ Comparison Error
         │    ├─→ No Versions → Show empty state
         │    ├─→ Invalid Selection → Show validation message
         │    └─→ Processing Error → Show error details
         │
         └─→ Unknown Error
              └─→ Log error + Show generic message
```

## State Management

```
┌─────────────────────────────────────────────────────────────┐
│                 Streamlit Session State                     │
└─────────────────────────────────────────────────────────────┘

st.session_state = {
    'selected_case_id': str,           # Current case ID
    'versions_loaded': bool,           # Whether versions are loaded
    'selected_versions': List[str],    # Selected S3 keys
    'run_comparison': bool,            # Trigger comparison
    'comparison_results': Dict,        # Comparison output
    'report_bytes': bytes,             # Generated report
    'report_format': str,              # 'html' or 'pdf'
}

State Transitions:
    Initial → Case Selected → Versions Loaded → 
    Versions Selected → Comparison Running → 
    Results Ready → Report Downloaded
```

---

This architecture provides:
- ✅ Clear separation of concerns
- ✅ Modular and testable components
- ✅ Scalable design
- ✅ Robust error handling
- ✅ Efficient data flow

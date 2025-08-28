# S3 Integration for OCR Streamlit App

This document explains how to set up and use the S3 integration in your OCR Streamlit application.

## Overview

The app now integrates with AWS S3 to fetch PDF reports instead of relying on local files. This allows for:
- Scalable storage of reports
- Easy access to historical reports
- Comparison of different report versions
- Future integration with n8n workflows

## Current Implementation

### What's Working Now
1. **Case Report Page**: Takes case ID input and simulates report generation
2. **Generating Report Page**: Shows static animation (no n8n dependency)
3. **Results Page**: Fetches PDFs from S3 and displays them side by side:
   - Left: Ground Truth PDF
   - Middle: AI Generated Report PDF  
   - Right: Comparison Report PDF (selectable from dropdown)

### S3 File Structure Expected
```
ocr-reports-bucket/
├── case_1234/
│   ├── ground_truth.pdf
│   ├── generated_report.pdf
│   └── comparison/
│       ├── report_v1.pdf
│       ├── report_v2.pdf
│       └── report_v3.pdf
└── case_5678/
    ├── ground_truth.pdf
    ├── generated_report.pdf
    └── comparison/
        └── report_v1.pdf
```

## Setup Instructions

### Option 1: Environment Variables
Set these environment variables before running the app:

```bash
export AWS_ACCESS_KEY_ID=your_access_key_here
export AWS_SECRET_ACCESS_KEY=your_secret_key_here
export AWS_REGION=us-east-1
export S3_BUCKET_NAME=your-bucket-name
```

### Option 2: Configuration File
1. Copy `s3_config_example.yaml` to `s3_config.yaml`
2. Fill in your AWS credentials and bucket name
3. The app will automatically load this configuration

### Option 3: Demo Mode
If no S3 credentials are provided, the app will run in demo mode with mock data.

## Usage

### 1. Enter Case ID
- Go to the Case Report page
- Enter a 4-digit case ID (e.g., 1234)
- Click "Generate Report"

### 2. View Generation Animation
- The app will show a simulated report generation process
- This is currently static (no real n8n integration)

### 3. View Results
- Navigate to the Results page
- View three PDFs side by side:
  - **Ground Truth**: Original document
  - **Generated Report**: AI-generated analysis
  - **Comparison Report**: Select from dropdown to compare historical versions

## Future Integration with n8n

When you're ready to integrate n8n:

1. **Replace the simulation** in `pages/01_Case_Report.py` with actual n8n API calls
2. **Update the generation page** to show real progress from n8n
3. **Modify the S3 integration** to handle real-time file updates

The current S3 structure is designed to work seamlessly with n8n workflows that upload files to S3.

## Troubleshooting

### S3 Connection Issues
- Check your AWS credentials
- Verify the bucket name and region
- Ensure your IAM user has S3 read permissions

### PDF Display Issues
- Check that PDFs are properly uploaded to S3
- Verify the file naming convention matches the expected structure
- Check browser console for any JavaScript errors

### Demo Mode
If you see "Demo Mode" warnings, it means S3 credentials are not configured. The app will still work with mock data.

## File Structure

```
app/
├── s3_utils.py          # S3 integration logic
├── ui.py               # UI components
└── auth.py             # Authentication

pages/
├── 01_Case_Report.py   # Case ID input
├── 02_Generating_Report.py  # Generation animation
└── 03_Results.py       # PDF comparison view

s3_config_example.yaml  # S3 configuration template
```

## Testing

1. **Without S3**: The app will run in demo mode with mock data
2. **With S3**: Upload some test PDFs to your S3 bucket following the naming convention
3. **Case IDs**: Use any 4-digit number (e.g., 1234, 5678) to test the flow

## Next Steps

1. Set up your S3 bucket with the correct folder structure
2. Upload some sample PDFs for testing
3. Test the complete flow from case ID input to PDF comparison
4. When ready, integrate with n8n workflows

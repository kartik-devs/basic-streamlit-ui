# n8n + S3 Integration Guide for OCR Workflow

This guide explains how to integrate your existing n8n workflows with the S3 storage system for the OCR application.

## Your Current n8n Workflow Structure

Based on the screenshots, you have a comprehensive workflow with 8 sections:

### **Section 1**: Table of Contents + Section 1
- **Input**: Case data
- **Process**: AI Agent + Google Vertex Chat Model
- **Output**: Formatted Section 1

### **Section 2**: Complete Section 2 + Accuracy Metrics
- **Input**: Case data
- **Process**: HTTP POST → Code → AI Agent → Airtable storage
- **Output**: Section 2 + accuracy metrics

### **Section 3**: Patient Intake Data + AI Generation
- **Input**: Zoho data from Snowflake
- **Process**: Data formatting → AI generation → Google Vertex Chat Model
- **Output**: Formatted Section 3

### **Section 4**: Complete Section 4 + Ground Truth Comparison
- **Input**: Case data
- **Process**: HTTP request → Code → AI Agent1 → AI Agent2 → Airtable
- **Output**: Section 4 + accuracy metrics

### **Section 5-7**: Sequential Processing Pipeline
- **Flow**: Section 5 → Section 6 → Section 7
- **Process**: Creating → Formatting for each section

### **Section 8**: Gender-Based Conditional Processing
- **Input**: Case data with gender condition
- **Process**: If Female → Female Section 8, If Male → Male Section 8
- **Output**: Gender-specific Section 8

## S3 Integration Points

### 1. **File Upload After Each Section**
Add S3 upload nodes after each section completion:

```javascript
// Example: After Section 1 completion
{
  "operation": "upload",
  "resource": "s3",
  "bucket": "ocr-reports-bucket",
  "key": "case_{{ $json.case_id }}/generated_reports/section_1.pdf",
  "content": "{{ $json.section_1_pdf_content }}"
}
```

### 2. **Complete Report Generation**
After all sections are complete, combine them into a single PDF:

```javascript
// Example: Combine all sections
{
  "operation": "upload",
  "resource": "s3",
  "bucket": "ocr-reports-bucket",
  "key": "case_{{ $json.case_id }}/generated_reports/complete_report.pdf",
  "content": "{{ $json.combined_pdf_content }}"
}
```

### 3. **Metadata Storage**
Store workflow execution data:

```javascript
// Example: Store generation log
{
  "operation": "upload",
  "resource": "s3",
  "bucket": "ocr-reports-bucket",
  "key": "case_{{ $json.case_id }}/metadata/generation_log.json",
  "content": "{{ JSON.stringify($json.execution_log) }}"
}
```

## Recommended n8n Modifications

### **Add S3 Upload Nodes**

1. **After Section 1**: Upload `section_1.pdf`
2. **After Section 2**: Upload `section_2.pdf` + accuracy metrics
3. **After Section 3**: Upload `section_3.pdf`
4. **After Section 4**: Upload `section_4.pdf` + comparison data
5. **After Section 5**: Upload `section_5.pdf`
6. **After Section 6**: Upload `section_6.pdf`
7. **After Section 7**: Upload `section_7.pdf`
8. **After Section 8**: Upload `section_8.pdf`
9. **Final Step**: Combine all sections → Upload `complete_report.pdf`

### **Add Version Control**

For comparison reports, add a versioning system:

```javascript
// Example: Version control
{
  "operation": "upload",
  "resource": "s3",
  "bucket": "ocr-reports-bucket",
  "key": "case_{{ $json.case_id }}/comparison_reports/v{{ $json.version }}_{{ $now.format('YYYY-MM-DD') }}/complete_report.pdf",
  "content": "{{ $json.complete_report_content }}"
}
```

## Implementation Steps

### **Step 1: Add S3 Credentials to n8n**
1. Go to n8n Settings → Credentials
2. Add AWS S3 credentials
3. Configure bucket name and region

### **Step 2: Add S3 Upload Nodes**
1. Add S3 upload node after each section completion
2. Configure file paths according to the structure
3. Map data from previous nodes

### **Step 3: Add Error Handling**
1. Add error handling for S3 uploads
2. Implement retry logic for failed uploads
3. Log upload status to metadata

### **Step 4: Test Integration**
1. Run workflow with test case ID
2. Verify files are uploaded to S3
3. Check Streamlit UI can fetch and display files

## Example n8n Node Configuration

### **S3 Upload Node (Section 1)**
```json
{
  "name": "Upload Section 1 to S3",
  "type": "n8n-nodes-base.awsS3",
  "parameters": {
    "operation": "upload",
    "bucket": "ocr-reports-bucket",
    "key": "case_{{ $json.case_id }}/generated_reports/section_1.pdf",
    "binaryData": true,
    "binaryPropertyName": "section_1_pdf"
  }
}
```

### **HTTP Request Node (Trigger)**
```json
{
  "name": "Trigger from Streamlit",
  "type": "n8n-nodes-base.httpTrigger",
  "parameters": {
    "httpMethod": "POST",
    "path": "generate-report",
    "responseMode": "responseNode"
  }
}
```

## Streamlit Integration

The Streamlit UI is already configured to:
1. **Fetch files** from the new S3 structure
2. **Display sections** individually or as complete report
3. **Show comparison** reports from different versions
4. **Handle metadata** files for additional information

## Testing the Integration

### **1. Manual Test**
1. Upload test PDFs to S3 manually
2. Test Streamlit UI with case ID
3. Verify all three columns display correctly

### **2. n8n Test**
1. Run n8n workflow with test case
2. Verify files are uploaded to S3
3. Test Streamlit UI with the generated case ID

### **3. End-to-End Test**
1. Enter case ID in Streamlit
2. Trigger n8n workflow
3. Wait for completion
4. View results in Streamlit

## Troubleshooting

### **Common Issues**
1. **S3 Upload Failures**: Check AWS credentials and permissions
2. **File Not Found**: Verify S3 key paths match expected structure
3. **PDF Display Issues**: Ensure PDFs are properly formatted
4. **Version Conflicts**: Check case ID uniqueness

### **Debug Steps**
1. Check n8n execution logs
2. Verify S3 bucket contents
3. Test S3 access from Streamlit
4. Check file permissions and formats

## Next Steps

1. **Implement S3 uploads** in your n8n workflows
2. **Test with sample data** to verify integration
3. **Deploy to production** when ready
4. **Monitor upload success rates** and performance

The S3 structure is designed to work seamlessly with your existing n8n workflow while providing a clean, organized storage system for all generated reports and metadata.

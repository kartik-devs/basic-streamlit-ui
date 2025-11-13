# LCP Version Comparison Feature

## Overview

The Version Comparison feature allows you to compare different versions of Life Care Plan (LCP) documents for a specific case, providing detailed section-by-section analysis of changes.

## Features

### 1. **Two Comparison Modes**

#### Selective Comparison 🎯
- Choose specific versions to compare (e.g., version 3, 4, and 10)
- Ideal for comparing non-consecutive versions
- Provides focused comparison between selected documents

#### Overall Comparison 📊
- Compares all available versions sequentially
- Shows the evolution of the document over time
- Useful for tracking complete document history

### 2. **Section-by-Section Analysis**

The system automatically:
- Extracts sections from each PDF document
- Identifies added, removed, and modified content
- Highlights specific line-level changes
- Provides summary statistics

### 3. **Multiple Output Formats**

- **HTML Report**: Interactive, scrollable report with color-coded changes
- **PDF Report**: Printable, professional format for documentation

### 4. **Visual Indicators**

- ✅ **Added**: New content in green
- ❌ **Removed**: Deleted content in red
- 🔄 **Modified**: Changed content in yellow
- ℹ️ **Unchanged**: No changes detected

## Installation

### 1. Install Required Dependencies

```bash
pip install -r requirements.txt
```

The following new packages are required:
- `PyPDF2==3.0.1` - PDF text extraction
- `pdfplumber==0.10.3` - Alternative PDF processing
- `reportlab==4.0.7` - PDF report generation

### 2. Verify S3 Configuration

Ensure your S3 credentials are properly configured in:
- Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- Or `config/s3_config.yaml`

## Usage

### Step 1: Navigate to Version Comparison

From the main dashboard, click the **🔄 Version Compare** button or use the sidebar to navigate to "Version Comparison".

### Step 2: Select a Case

1. Enter or select a case ID (e.g., 3424)
2. Click **🔍 Load Versions** to fetch available LCP documents

### Step 3: Choose Comparison Mode

**Selective Comparison:**
1. Select the "Selective Comparison" radio button
2. Check the boxes next to the versions you want to compare
3. At least 2 versions must be selected

**Overall Comparison:**
1. Select the "Overall Comparison" radio button
2. All versions will be compared automatically

### Step 4: Generate Report

1. Choose output format (HTML or PDF)
2. Click **🚀 Generate Comparison**
3. Wait for processing to complete

### Step 5: Review and Download

1. View the summary statistics (Total, Added, Removed, Modified sections)
2. Preview the report in the browser
3. Download the report using the **📥 Download** button

## Technical Details

### Document Detection

The system looks for LCP documents matching these patterns:
- `{timestamp}-{case_id}-CompleteAIGeneratedReport.pdf`
- Files containing "LCP" or "LifeCarePlan" in the filename
- Located in `{case_id}/Output/` folder in S3

### Section Extraction

Sections are identified using common patterns:
- `Section 1: Title`
- `1. Title`
- `SECTION 1 - Title`
- `Part I: Title`

If no sections are detected, the entire document is treated as one section.

### Comparison Algorithm

1. **Text Extraction**: Extract text from each PDF using PyPDF2/pdfplumber
2. **Section Parsing**: Identify and separate document sections
3. **Diff Generation**: Use Python's `difflib` to compare text line-by-line
4. **Change Classification**: Categorize changes as added, removed, or modified
5. **Report Generation**: Create formatted HTML or PDF output

## File Structure

```
app/
├── version_comparison.py       # Core comparison logic
└── s3_utils.py                 # S3 integration (existing)

pages/
└── 06_Version_Comparison.py    # UI page

requirements.txt                # Updated dependencies
```

## API Reference

### LCPVersionComparator Class

```python
from app.version_comparison import LCPVersionComparator
from app.s3_utils import get_s3_manager

# Initialize
s3_manager = get_s3_manager()
comparator = LCPVersionComparator(s3_manager)

# Get available versions
versions = comparator.get_lcp_versions(case_id="3424")

# Compare versions
results = comparator.compare_versions(
    case_id="3424",
    version_keys=["3424/Output/file1.pdf", "3424/Output/file2.pdf"],
    mode="selective"  # or "all"
)

# Generate report
report_bytes = comparator.generate_comparison_report(
    results,
    output_format="html"  # or "pdf"
)
```

## Troubleshooting

### Issue: No versions found

**Solution:**
- Verify the case ID is correct
- Check that LCP documents exist in `{case_id}/Output/` folder
- Ensure S3 connection is working

### Issue: PDF extraction fails

**Solution:**
- Install both PyPDF2 and pdfplumber: `pip install PyPDF2 pdfplumber`
- Check that PDFs are not corrupted or password-protected
- Verify PDF files are text-based (not scanned images)

### Issue: Comparison takes too long

**Solution:**
- Use selective comparison instead of overall for large document sets
- Ensure good network connection to S3
- Consider comparing fewer versions at once

### Issue: Sections not detected

**Solution:**
- The system will treat the entire document as one section
- Manual section headers may need to follow standard patterns
- Check if PDFs have proper text structure (not images)

## Performance Considerations

- **Small PDFs (<5MB)**: ~5-10 seconds per comparison
- **Medium PDFs (5-20MB)**: ~15-30 seconds per comparison
- **Large PDFs (>20MB)**: ~30-60 seconds per comparison

Processing time scales with:
- Number of versions being compared
- Size of PDF files
- Complexity of document structure
- Network speed to S3

## Future Enhancements

Potential improvements for future versions:

1. **Visual Diff**: Side-by-side PDF comparison with highlighting
2. **Export Options**: JSON, CSV, Excel formats
3. **Scheduled Comparisons**: Automatic comparison on new version upload
4. **Email Notifications**: Send comparison reports via email
5. **Version Annotations**: Add notes/comments to specific versions
6. **Batch Processing**: Compare multiple cases at once
7. **AI Summary**: LLM-generated summary of key changes

## Support

For issues or questions:
1. Check this README first
2. Review error messages in the UI
3. Check application logs
4. Contact the development team

## License

Part of the CaseTracker Pro system.

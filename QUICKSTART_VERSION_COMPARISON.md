# Quick Start Guide - Version Comparison Feature

## Installation (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- PyPDF2 (PDF text extraction)
- pdfplumber (Alternative PDF processing)
- reportlab (PDF report generation)

### Step 2: Verify Installation

```bash
python test_version_comparison.py
```

You should see all tests pass ✅

### Step 3: Start the Application

```bash
streamlit run main.py
```

## Usage (2 minutes)

### Quick Comparison

1. **Navigate**: Click **🔄 Version Compare** on the home page
2. **Select Case**: Enter case ID (e.g., `3424`) and click **🔍 Load Versions**
3. **Choose Mode**: 
   - **Selective**: Check 2+ versions to compare
   - **Overall**: Compare all versions automatically
4. **Generate**: Click **🚀 Generate Comparison**
5. **Download**: Click **📥 Download** to save the report

## Example Use Cases

### Use Case 1: Compare Latest Two Versions
**Goal**: See what changed in the most recent update

1. Select case ID: `3424`
2. Choose "Selective Comparison"
3. Check the two most recent versions
4. Generate HTML report
5. Review changes section-by-section

### Use Case 2: Track Document Evolution
**Goal**: See all changes across all versions

1. Select case ID: `3424`
2. Choose "Overall Comparison"
3. Generate PDF report
4. Download for documentation

### Use Case 3: Compare Specific Versions
**Goal**: Compare version 3, 4, and 10 only

1. Select case ID: `3424`
2. Choose "Selective Comparison"
3. Check versions 3, 4, and 10
4. Generate HTML report
5. Review specific changes

## Understanding the Report

### Color Codes
- 🟢 **Green (Added)**: New content added
- 🔴 **Red (Removed)**: Content deleted
- 🟡 **Yellow (Modified)**: Content changed
- 🔵 **Blue (Unchanged)**: No changes

### Statistics
- **Total Sections**: Number of sections analyzed
- **Added**: New sections in newer version
- **Removed**: Sections deleted from older version
- **Modified**: Sections with changes

### Report Sections
Each section shows:
- Section name and status badge
- Added lines (if any)
- Removed lines (if any)
- Modified lines with old/new comparison

## Troubleshooting

### Problem: "No versions found"
**Solution**: 
- Verify case ID is correct
- Check S3 connection
- Ensure LCP documents exist in `{case_id}/Output/` folder

### Problem: "Need at least 2 valid versions"
**Solution**:
- Select at least 2 versions in selective mode
- Ensure PDFs are valid and not corrupted

### Problem: Installation fails
**Solution**:
```bash
# Upgrade pip first
python -m pip install --upgrade pip

# Install packages one by one
pip install PyPDF2
pip install pdfplumber
pip install reportlab
```

## Tips & Best Practices

### Performance Tips
- Use **Selective** mode for faster comparisons
- Compare 2-3 versions at a time for best performance
- Use **HTML** format for quick viewing
- Use **PDF** format for archiving/printing

### Comparison Tips
- Compare consecutive versions to track incremental changes
- Use overall mode to see document evolution
- Download reports for documentation purposes
- Review statistics before diving into details

### Workflow Tips
1. Start with overall comparison to get big picture
2. Use selective comparison to focus on specific versions
3. Export HTML for team review
4. Export PDF for client documentation

## Advanced Features

### Programmatic Access

```python
from app.version_comparison import LCPVersionComparator
from app.s3_utils import get_s3_manager

# Initialize
s3_manager = get_s3_manager()
comparator = LCPVersionComparator(s3_manager)

# Get versions
versions = comparator.get_lcp_versions("3424")

# Compare
results = comparator.compare_versions(
    case_id="3424",
    version_keys=[v['s3_key'] for v in versions[:2]],
    mode="selective"
)

# Generate report
report = comparator.generate_comparison_report(results, "html")
```

### Custom Section Patterns

Edit `app/version_comparison.py` to add custom section patterns:

```python
section_patterns = [
    r'(?:Section|SECTION)\s+(\d+)[:\-\s]+([^\n]+)',
    r'^(\d+)\.\s+([A-Z][^\n]+)',
    r'(?:Part|PART)\s+([IVX]+)[:\-\s]+([^\n]+)',
    # Add your custom pattern here
]
```

## Next Steps

1. ✅ Test with a real case ID
2. ✅ Generate your first comparison report
3. ✅ Share reports with your team
4. ✅ Integrate into your workflow

## Support

- 📖 Full documentation: `VERSION_COMPARISON_README.md`
- 🧪 Test script: `python test_version_comparison.py`
- 🐛 Issues: Check application logs and error messages

---

**Ready to start?** Run `streamlit run main.py` and click **🔄 Version Compare**!

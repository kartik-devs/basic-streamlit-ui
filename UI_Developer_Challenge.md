# UI Developer Challenge

## Overview
This challenge is designed to assess your UI development skills, API integration capabilities, and ability to work with cloud services. You will build a simple web application that integrates with n8n workflow automation and displays reports from AWS S3.

## Challenge Description

### Objective
Create a web application that:
1. Provides a user interface to trigger n8n workflows
2. Fetches report files from AWS S3
3. Displays the report data in a user-friendly format

### Requirements

#### Core Functionality
1. **Workflow Trigger Interface**
   - Create a UI with a button/form to trigger an n8n workflow
   - Display workflow execution status (pending, running, completed, failed)
   - Show appropriate loading states and feedback messages

2. **Report Fetching**
   - Fetch report files from AWS S3 (you can use mock data or a provided S3 bucket)
   - Support common report formats (CSV, JSON, or PDF)
   - Handle errors gracefully (file not found, network errors, etc.)

3. **Report Display**
   - Display the fetched report in a clean, readable format
   - For tabular data: implement sorting and basic filtering
   - For PDF reports: provide a viewer or download option
   - Ensure responsive design (mobile and desktop)

4. **User Experience**
   - Clean, modern UI design
   - Intuitive navigation
   - Loading indicators for async operations
   - Error messages that are user-friendly
   - Success notifications

#### Technical Requirements
- **Framework**: Any modern UI framework of your choice (React, Vue, Angular, Svelte, Streamlit, etc.)
- **n8n Integration**: Use n8n webhooks or API to trigger workflows
- **S3 Integration**: Use AWS SDK or pre-signed URLs to fetch reports
- **Code Quality**: Clean, well-organized, and commented code
- **Documentation**: README with setup instructions

### Deliverables

1. **Source Code**
   - Complete application code
   - Configuration files
   - Package/dependency management files

2. **Documentation**
   - README.md with:
     - Setup instructions
     - How to run the application
     - Environment variables needed
     - Architecture overview
     - Any assumptions made

3. **Demo**
   - Screenshots or video walkthrough (optional but appreciated)
   - Deployed version (optional, can use Vercel, Netlify, Streamlit Cloud, etc.)

### Evaluation Criteria

| Criteria | Weight | Description |
|----------|--------|-------------|
| **Functionality** | 30% | Does the application meet all core requirements? |
| **Code Quality** | 25% | Is the code clean, maintainable, and well-structured? |
| **UI/UX Design** | 20% | Is the interface intuitive and visually appealing? |
| **Error Handling** | 15% | Are edge cases and errors handled gracefully? |
| **Documentation** | 10% | Is the setup process clear and well-documented? |

### Time Limit
**3-4 hours** (We understand you may have other commitments, so complete it within a week)

### Getting Started

#### n8n Setup (Mock)
If you don't have access to n8n, you can:
- Set up a free n8n.cloud account
- Use n8n desktop version locally
- Mock the n8n API responses for demonstration

Example n8n webhook endpoint:
```
POST https://your-n8n-instance.com/webhook/generate-report
```

#### S3 Setup (Mock)
If you don't have AWS access, you can:
- Use mock JSON/CSV data stored locally
- Use a public S3 bucket (we can provide one)
- Simulate S3 responses with local files

Example report structure (JSON):
```json
{
  "report_id": "RPT-2024-001",
  "generated_at": "2024-01-15T10:30:00Z",
  "data": [
    {"id": 1, "name": "Item 1", "value": 100, "status": "active"},
    {"id": 2, "name": "Item 2", "value": 250, "status": "pending"}
  ],
  "summary": {
    "total_items": 2,
    "total_value": 350
  }
}
```

### Bonus Points (Optional)

- **Authentication**: Add simple user authentication
- **Real-time Updates**: Use WebSockets for live workflow status updates
- **Data Visualization**: Add charts/graphs for report data
- **Testing**: Include unit or integration tests
- **Accessibility**: WCAG compliance
- **Dark Mode**: Theme switching capability

### Submission

Please submit your solution via:
- GitHub repository (preferred)
- ZIP file with all source code
- Include a README.md with setup instructions

### Questions?

If you have any questions during the challenge, please reach out to [contact email/person].

---

**Good luck! We're excited to see your solution! 🚀**

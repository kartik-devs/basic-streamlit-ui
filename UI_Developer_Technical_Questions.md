# UI Developer - Technical Interview Questions

## Section 1: Core UI/Frontend Development (15-20 minutes)

### HTML/CSS Fundamentals

1. **Question**: Explain the CSS Box Model and how `box-sizing: border-box` differs from the default behavior.
   - **Follow-up**: How would you center a div both horizontally and vertically?

2. **Question**: What is the difference between `display: none`, `visibility: hidden`, and `opacity: 0`?
   - **Expected**: Understanding of rendering, layout, and accessibility implications

3. **Question**: Explain Flexbox vs Grid. When would you use one over the other?
   - **Follow-up**: How would you create a responsive 3-column layout that stacks on mobile?

4. **Question**: What are CSS custom properties (variables) and what advantages do they offer?

### JavaScript/TypeScript

5. **Question**: Explain the difference between `let`, `const`, and `var`. What is hoisting?

6. **Question**: What is the difference between `==` and `===` in JavaScript?
   - **Follow-up**: What is the output of `[] == ![]` and why?

7. **Question**: Explain Promises and async/await. How do they differ?
   ```javascript
   // What's the output order?
   console.log('1');
   setTimeout(() => console.log('2'), 0);
   Promise.resolve().then(() => console.log('3'));
   console.log('4');
   ```

8. **Question**: What is event bubbling and event capturing? How do you stop event propagation?

9. **Question**: Explain closures in JavaScript with a practical example.

10. **Question**: What is the difference between `null` and `undefined`?

## Section 2: Modern Frontend Frameworks (15-20 minutes)

### React (or their preferred framework)

11. **Question**: Explain the Virtual DOM and how React uses it for performance optimization.

12. **Question**: What is the difference between state and props in React?
    - **Follow-up**: When would you lift state up?

13. **Question**: Explain React hooks. What are `useState`, `useEffect`, and `useCallback` used for?
    ```javascript
    // What's wrong with this code?
    function Component() {
      const [count, setCount] = useState(0);
      useEffect(() => {
        setCount(count + 1);
      }, []);
    }
    ```

14. **Question**: How do you handle side effects in React? Give examples.

15. **Question**: What is prop drilling and how can you avoid it?
    - **Expected**: Context API, Redux, Zustand, or other state management solutions

### State Management

16. **Question**: When would you use a global state management library (Redux, Zustand, etc.) vs local component state?

17. **Question**: Explain the concept of immutability in state management. Why is it important?

## Section 3: API Integration & Async Operations (10-15 minutes)

18. **Question**: How do you handle API calls in a frontend application?
    - **Follow-up**: How do you handle loading states, errors, and retries?

19. **Question**: What is CORS and why does it exist? How do you handle CORS issues?

20. **Question**: Explain the difference between REST and GraphQL. What are the pros/cons of each?

21. **Question**: How would you implement authentication in a frontend application?
    - **Expected**: JWT tokens, refresh tokens, secure storage, protected routes

22. **Question**: What is the difference between GET and POST requests? When would you use PUT vs PATCH?

## Section 4: n8n & Workflow Automation (10 minutes)

23. **Question**: Have you worked with workflow automation tools before? If yes, which ones?

24. **Question**: How would you trigger an n8n workflow from a web application?
    - **Expected**: Webhooks, HTTP requests, API calls

25. **Question**: How would you handle long-running workflow executions in the UI?
    - **Expected**: Polling, WebSockets, loading states, notifications

26. **Question**: If an n8n workflow fails, how would you display this to the user and allow them to retry?

## Section 5: AWS S3 & File Handling (10 minutes)

27. **Question**: How would you fetch a file from AWS S3 in a web application?
    - **Expected**: AWS SDK, pre-signed URLs, direct API calls

28. **Question**: What are pre-signed URLs and when would you use them?
    - **Expected**: Security, temporary access, avoiding credentials in frontend

29. **Question**: How would you display different file types (CSV, JSON, PDF) in the browser?
    - **Expected**: File parsing, libraries (Papa Parse, PDF.js), blob URLs

30. **Question**: How would you handle large file downloads in the UI?
    - **Expected**: Progress indicators, streaming, chunking, error handling

## Section 6: Performance & Optimization (10 minutes)

31. **Question**: What techniques would you use to optimize the performance of a web application?
    - **Expected**: Code splitting, lazy loading, memoization, debouncing, throttling

32. **Question**: Explain lazy loading and code splitting. How do they improve performance?

33. **Question**: What is debouncing and throttling? Give use cases for each.
    ```javascript
    // Implement a simple debounce function
    function debounce(func, delay) {
      // Your implementation
    }
    ```

34. **Question**: How would you optimize rendering of a large list (1000+ items)?
    - **Expected**: Virtualization, pagination, infinite scroll

35. **Question**: What tools would you use to measure and debug performance issues?
    - **Expected**: Chrome DevTools, Lighthouse, React DevTools, Performance API

## Section 7: Testing & Quality (5-10 minutes)

36. **Question**: What types of testing are important for frontend applications?
    - **Expected**: Unit, integration, e2e, visual regression

37. **Question**: Have you used testing libraries? Which ones and for what purpose?
    - **Expected**: Jest, React Testing Library, Cypress, Playwright, Vitest

38. **Question**: How do you test components that make API calls?
    - **Expected**: Mocking, MSW (Mock Service Worker), test fixtures

## Section 8: Responsive Design & Accessibility (5-10 minutes)

39. **Question**: How do you approach responsive design?
    - **Expected**: Mobile-first, breakpoints, flexible layouts, media queries

40. **Question**: What is accessibility (a11y) and why is it important?
    - **Follow-up**: What are ARIA attributes and when would you use them?

41. **Question**: How do you ensure your application is keyboard navigable?

42. **Question**: What tools do you use to test accessibility?
    - **Expected**: Lighthouse, axe DevTools, screen readers, WAVE

## Section 9: Problem-Solving & Coding Exercise (15-20 minutes)

### Coding Exercise 1: Data Transformation
```javascript
// Given an array of reports from S3, transform it to group by status
const reports = [
  { id: 1, name: 'Report A', status: 'completed', date: '2024-01-01' },
  { id: 2, name: 'Report B', status: 'pending', date: '2024-01-02' },
  { id: 3, name: 'Report C', status: 'completed', date: '2024-01-03' },
  { id: 4, name: 'Report D', status: 'failed', date: '2024-01-04' }
];

// Expected output:
// {
//   completed: [{ id: 1, ... }, { id: 3, ... }],
//   pending: [{ id: 2, ... }],
//   failed: [{ id: 4, ... }]
// }

// Write a function to transform this data
```

### Coding Exercise 2: Custom Hook (React)
```javascript
// Create a custom React hook called useS3Report that:
// 1. Fetches a report from S3 given a reportId
// 2. Returns { data, loading, error, refetch }
// 3. Handles loading and error states

function useS3Report(reportId) {
  // Your implementation
}
```

### Coding Exercise 3: Debounce Implementation
```javascript
// Implement a debounce function that delays execution
// until after a specified time has elapsed since the last call

function debounce(func, delay) {
  // Your implementation
}

// Usage example:
const searchAPI = debounce((query) => {
  console.log('Searching for:', query);
}, 300);
```

## Section 10: System Design & Architecture (10 minutes)

43. **Question**: Design a frontend architecture for a dashboard that displays real-time reports from multiple sources (S3, databases, APIs).
    - **Expected**: Component structure, state management, data flow, caching strategy

44. **Question**: How would you structure a large-scale React application?
    - **Expected**: Folder structure, component organization, shared utilities, routing

45. **Question**: Explain your approach to error handling and logging in a production application.

46. **Question**: How would you implement a notification system that shows workflow status updates?
    - **Expected**: Toast notifications, WebSockets, polling, state management

## Behavioral & Scenario-Based Questions

47. **Question**: Describe a challenging UI bug you encountered and how you solved it.

48. **Question**: How do you stay updated with the latest frontend technologies and best practices?

49. **Question**: Tell me about a time you had to optimize a slow-performing application.

50. **Question**: How do you handle disagreements about UI/UX decisions with designers or product managers?

---

## Scoring Guide

### Junior Level (0-2 years)
- Should answer 60-70% of Section 1-2 correctly
- Basic understanding of API integration
- Familiar with at least one modern framework

### Mid Level (2-4 years)
- Should answer 70-80% of Section 1-5 correctly
- Good understanding of performance optimization
- Experience with testing and accessibility
- Can complete coding exercises with minimal hints

### Senior Level (4+ years)
- Should answer 80-90% of all sections correctly
- Deep understanding of architecture and design patterns
- Strong problem-solving skills
- Can discuss trade-offs and best practices
- Leadership and mentoring experience

---

## Notes for Interviewers

- Adjust questions based on the candidate's experience level
- Focus more on their preferred framework/technology stack
- Allow candidates to ask clarifying questions
- Look for thought process, not just correct answers
- Assess communication skills and ability to explain complex concepts
- Be flexible with coding exercises - syntax matters less than logic

**Time Allocation**: 60-90 minutes total interview

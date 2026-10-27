# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: rag-evaluation.spec.ts >> E2E Full Flow with Groq Evaluation
- Location: tests\e2e\rag-evaluation.spec.ts:70:5

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('.assistant-markdown').last().locator('xpath=following-sibling::div[contains(., "Citations:")]')
Expected: visible
Timeout: 10000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 10000ms
  - waiting for locator('.assistant-markdown').last().locator('xpath=following-sibling::div[contains(., "Citations:")]')

```

```yaml
- complementary:
  - heading "Knowledge Agent" [level=1]
  - navigation:
    - button "💬 Ask"
    - button "📚 Library"
    - button "🧠 Knowledge"
    - button "✅ Review"
    - button "⚙️ Settings"
  - text: e2e-user-1786183772945@example.com
  - button "🚪"
- main:
  - heading "Ask & Chat" [level=2]
  - text: Online
  - heading "Chat With Your Knowledge Base" [level=2]
  - paragraph: Responses are grounded in retrieved chunks.
  - button "+ New Chat"
  - list:
    - listitem:
      - text: New Chat
      - button "Delete"
  - text: "Error: Retrieval failed: '_type'"
  - paragraph: What is the project codename and backup format?
  - combobox:
    - option "All Documents" [selected]
    - option "E2E Text Fixture 1786183772945"
    - option "E2E PDF Fixture 1786183772945"
  - textbox "Ask a question..."
  - button "Send" [disabled]
- alert
```

# Test source

```ts
  30  |   const groq = new Groq({ apiKey: groqApiKey });
  31  | 
  32  |   const prompt = `
  33  |     You are an evaluator grading a Retrieval-Augmented Generation (RAG) system.
  34  |     Evaluate the following answer based on the provided expected facts and whether it properly cited its sources.
  35  | 
  36  |     Question: ${question}
  37  |     Expected Facts: ${expectedFacts}
  38  |     Answer to Grade: ${retrievedAnswer}
  39  |     Citations provided in UI: ${citationsText}
  40  | 
  41  |     Return your evaluation as strict JSON with this exact schema:
  42  |     {
  43  |       "passed": boolean,
  44  |       "correctness_score": float between 0.0 and 1.0,
  45  |       "usefulness_score": float between 0.0 and 1.0,
  46  |       "groundedness_score": float between 0.0 and 1.0,
  47  |       "missing_facts": [string],
  48  |       "unsupported_claims": [string],
  49  |       "reason": "short explanation string"
  50  |     }
  51  | 
  52  |     Scoring criteria:
  53  |     - correctness_score: Are the facts presented correct according to the Expected Facts?
  54  |     - usefulness_score: Is it a helpful and direct answer to the user's question?
  55  |     - groundedness_score: Is the answer fully supported by the provided citations and expected facts? (No hallucination).
  56  |     - passed: Must be true if correctness >= 0.8, usefulness >= 0.75, groundedness >= 0.8, and citations are present.
  57  |   `;
  58  | 
  59  |   const chatCompletion = await groq.chat.completions.create({
  60  |     messages: [{ role: 'user', content: prompt }],
  61  |     model: 'llama-3.3-70b-versatile',
  62  |     temperature: 0,
  63  |     response_format: { type: 'json_object' }
  64  |   });
  65  | 
  66  |   const content = chatCompletion.choices[0].message.content;
  67  |   return JSON.parse(content || '{}');
  68  | }
  69  | 
  70  | test('E2E Full Flow with Groq Evaluation', async ({ page }) => {
  71  |   const timestamp = Date.now();
  72  |   const testEmail = `e2e-user-${timestamp}@example.com`;
  73  |   const textFixturePath = path.join(__dirname, 'fixtures', 'facts.txt');
  74  |   const pdfFixturePath = path.join(__dirname, 'fixtures', 'facts.pdf');
  75  | 
  76  |   // 1. Register — navigate to the register mode first for a brand-new e2e email,
  77  |   //    then fill credentials and submit.
  78  |   await page.goto('/');
  79  |   // The toggle button text in AuthPanel.tsx is "Register here"
  80  |   await page.click('button:has-text("Register here")');
  81  |   await page.fill('input[type="email"]', testEmail);
  82  |   await page.fill('input[type="password"]', 'e2e-test-password');
  83  |   await page.click('button[type="submit"]');
  84  | 
  85  |   // Wait for login to complete (Ask & Chat should appear)
  86  |   await expect(page.locator('h2:has-text("Ask & Chat")')).toBeVisible({ timeout: 15000 });
  87  | 
  88  |   // 2. Upload text fixture
  89  |   await page.click('button:has-text("📚 Library")');
  90  |   await expect(page.locator('h2:has-text("Document Library")').first()).toBeVisible();
  91  |   
  92  |   await page.setInputFiles('input[type="file"]', textFixturePath);
  93  |   await page.fill('input[placeholder="Leave blank to use filename"]', `E2E Text Fixture ${timestamp}`);
  94  |   await page.click('form.create-doc-form button[type="submit"]');
  95  |   
  96  |   // Wait for indexing to complete for text fixture
  97  |   await expect(page.locator(`tr:has-text("E2E Text Fixture ${timestamp}")`).locator('.status-ready')).toBeVisible({ timeout: 30000 });
  98  | 
  99  |   // 3. Upload PDF fixture
  100 |   await page.setInputFiles('input[type="file"]', pdfFixturePath);
  101 |   await page.fill('input[placeholder="Leave blank to use filename"]', `E2E PDF Fixture ${timestamp}`);
  102 |   await page.click('form.create-doc-form button[type="submit"]');
  103 |   
  104 |   // Wait for indexing to complete for PDF fixture
  105 |   await expect(page.locator(`tr:has-text("E2E PDF Fixture ${timestamp}")`).locator('.status-ready')).toBeVisible({ timeout: 30000 });
  106 | 
  107 |   // 4. Ask a question about the text file
  108 |   await page.click('button:has-text("💬 Ask")');
  109 |   
  110 |   // Check if "New Chat" is needed or if we are already in an empty state
  111 |   const newChatBtn = page.locator('button:has-text("+ New Chat")');
  112 |   if (await newChatBtn.isVisible()) {
  113 |     await newChatBtn.click();
  114 |   }
  115 | 
  116 |   const textQuestion = 'What is the project codename and backup format?';
  117 |   await page.fill('input[placeholder="Ask a question..."]', textQuestion);
  118 |   await page.click('button:has-text("Send")');
  119 | 
  120 |   // Wait for assistant to answer and stop streaming (Send button becomes disabled because input is empty, but says 'Send' instead of 'Sending...')
  121 |   await expect(page.locator('button[type="submit"]', { hasText: 'Sending...' })).toHaveCount(0, { timeout: 60000 });
  122 | 
  123 |   // Extract answer text and citations
  124 |   // The answer is the last .assistant-markdown element
  125 |   const assistantAnswers = page.locator('.assistant-markdown');
  126 |   const textAnswerContent = await assistantAnswers.last().innerText();
  127 |   
  128 |   // Citations are usually in a ul below the assistant-markdown, in the same parent.
  129 |   const citationBlock = assistantAnswers.last().locator('xpath=following-sibling::div[contains(., "Citations:")]');
> 130 |   await expect(citationBlock).toBeVisible();
      |                               ^ Error: expect(locator).toBeVisible() failed
  131 |   const textCitations = await citationBlock.innerText();
  132 | 
  133 |   // 5. Evaluate Text Answer
  134 |   const textEval = await evaluateAnswer(
  135 |     textQuestion,
  136 |     "Project codename is Aster Notes, and Backup format is portable JSON bundle.",
  137 |     textAnswerContent,
  138 |     textCitations
  139 |   );
  140 | 
  141 |   expect(textEval.passed).toBe(true);
  142 |   expect(textEval.correctness_score).toBeGreaterThanOrEqual(0.8);
  143 |   expect(textEval.usefulness_score).toBeGreaterThanOrEqual(0.75);
  144 |   expect(textEval.groundedness_score).toBeGreaterThanOrEqual(0.8);
  145 | 
  146 |   // 6. Ask a question about the PDF
  147 |   const pdfQuestion = 'What are the required citation behavior and success metric for RAG evaluation?';
  148 |   await page.fill('input[placeholder="Ask a question..."]', pdfQuestion);
  149 |   await page.click('button:has-text("Send")');
  150 | 
  151 |   await expect(page.locator('button[type="submit"]', { hasText: 'Sending...' })).toHaveCount(0, { timeout: 60000 });
  152 |   
  153 |   const pdfAnswerContent = await assistantAnswers.last().innerText();
  154 |   const pdfCitationBlock = assistantAnswers.last().locator('xpath=following-sibling::div[contains(., "Citations:")]');
  155 |   await expect(pdfCitationBlock).toBeVisible();
  156 |   const pdfCitations = await pdfCitationBlock.innerText();
  157 | 
  158 |   // 7. Evaluate PDF Answer
  159 |   const pdfEval = await evaluateAnswer(
  160 |     pdfQuestion,
  161 |     "Required citation behavior is that answers must cite source chunks. Success metric is grounded, concise, and useful response.",
  162 |     pdfAnswerContent,
  163 |     pdfCitations
  164 |   );
  165 | 
  166 |   expect(pdfEval.passed).toBe(true);
  167 |   expect(pdfEval.correctness_score).toBeGreaterThanOrEqual(0.8);
  168 |   expect(pdfEval.usefulness_score).toBeGreaterThanOrEqual(0.75);
  169 |   expect(pdfEval.groundedness_score).toBeGreaterThanOrEqual(0.8);
  170 | 
  171 | });
  172 | 
```
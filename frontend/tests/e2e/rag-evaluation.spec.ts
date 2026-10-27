import { test, expect } from '@playwright/test';
import { Groq } from 'groq-sdk';
import path from 'path';

const groqApiKey = process.env.GROQ_API_KEY;

test.beforeAll(async () => {
  if (!groqApiKey) {
    console.warn('GROQ_API_KEY is missing. Groq evaluation tests will be skipped.');
  }

  // Poll until the backend is healthy before running any test.
  // The Docker Compose stack takes several seconds to fully initialize.
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch('http://localhost:8000/api/health');
      if (res.ok) return; // backend is ready
    } catch { /* still booting, ignore connection refused */ }
    await new Promise(r => setTimeout(r, 2000));
  }
  throw new Error('Backend did not become healthy within 60 seconds.');
});

async function evaluateAnswer(
  question: string,
  expectedFacts: string,
  retrievedAnswer: string,
  citationsText: string
) {
  const groq = new Groq({ apiKey: groqApiKey });

  const prompt = `
    You are an evaluator grading a Retrieval-Augmented Generation (RAG) system.
    Evaluate the following answer based on the provided expected facts and whether it properly cited its sources.

    Question: ${question}
    Expected Facts: ${expectedFacts}
    Answer to Grade: ${retrievedAnswer}
    Citations provided in UI: ${citationsText}

    Return your evaluation as strict JSON with this exact schema:
    {
      "passed": boolean,
      "correctness_score": float between 0.0 and 1.0,
      "usefulness_score": float between 0.0 and 1.0,
      "groundedness_score": float between 0.0 and 1.0,
      "missing_facts": [string],
      "unsupported_claims": [string],
      "reason": "short explanation string"
    }

    Scoring criteria:
    - correctness_score: Are the facts presented correct according to the Expected Facts?
    - usefulness_score: Is it a helpful and direct answer to the user's question?
    - groundedness_score: Is the answer fully supported by the provided citations and expected facts? (No hallucination).
    - passed: Must be true if correctness >= 0.8, usefulness >= 0.75, groundedness >= 0.8, and citations are present.
  `;

  const chatCompletion = await groq.chat.completions.create({
    messages: [{ role: 'user', content: prompt }],
    model: 'llama-3.3-70b-versatile',
    temperature: 0,
    response_format: { type: 'json_object' }
  });

  const content = chatCompletion.choices[0].message.content;
  return JSON.parse(content || '{}');
}

test('E2E Full Flow with Groq Evaluation', async ({ page }) => {
  test.skip(!groqApiKey, 'GROQ_API_KEY is required for E2E answer-quality tests.');
  const timestamp = Date.now();
  const testEmail = `e2e-user-${timestamp}@example.com`;
  const textFixturePath = path.join(__dirname, 'fixtures', 'facts.txt');
  const pdfFixturePath = path.join(__dirname, 'fixtures', 'facts.pdf');

  // 1. Register — navigate to the register mode first for a brand-new e2e email,
  //    then fill credentials and submit.
  await page.goto('/');
  // The toggle button text in AuthPanel.tsx is "Register here"
  await page.click('button:has-text("Register here")');
  await page.fill('input[type="email"]', testEmail);
  await page.fill('input[type="password"]', 'e2e-test-password');
  await page.click('button[type="submit"]');

  // Wait for login to complete (Ask & Chat should appear)
  await expect(page.locator('h2:has-text("Ask & Chat")')).toBeVisible({ timeout: 15000 });

  // 2. Upload text fixture
  await page.click('button:has-text("📚 Library")');
  await expect(page.locator('h2:has-text("Document Library")').first()).toBeVisible();
  
  await page.setInputFiles('input[type="file"]', textFixturePath);
  await page.fill('input[placeholder="Leave blank to use filename"]', `E2E Text Fixture ${timestamp}`);
  await page.click('form.create-doc-form button[type="submit"]');
  
  // Wait for indexing to complete for text fixture
  await expect(page.locator(`tr:has-text("E2E Text Fixture ${timestamp}")`).locator('.status-ready')).toBeVisible({ timeout: 30000 });

  // 3. Upload PDF fixture
  await page.setInputFiles('input[type="file"]', pdfFixturePath);
  await page.fill('input[placeholder="Leave blank to use filename"]', `E2E PDF Fixture ${timestamp}`);
  await page.click('form.create-doc-form button[type="submit"]');
  
  // Wait for indexing to complete for PDF fixture
  await expect(page.locator(`tr:has-text("E2E PDF Fixture ${timestamp}")`).locator('.status-ready')).toBeVisible({ timeout: 30000 });

  // 4. Ask a question about the text file
  await page.click('button:has-text("💬 Ask")');
  
  // Check if "New Chat" is needed or if we are already in an empty state
  const newChatBtn = page.locator('button:has-text("+ New Chat")');
  if (await newChatBtn.isVisible()) {
    await newChatBtn.click();
  }

  const textQuestion = 'What is the project codename and backup format?';
  await page.fill('input[placeholder="Ask a question..."]', textQuestion);
  await page.click('button:has-text("Send")');

  // Wait for assistant to answer and stop streaming (Send button becomes disabled because input is empty, but says 'Send' instead of 'Sending...')
  await expect(page.locator('button[type="submit"]', { hasText: 'Sending...' })).toHaveCount(0, { timeout: 60000 });

  // Extract answer text and citations
  // The answer is the last .assistant-markdown element
  const assistantAnswers = page.locator('.assistant-markdown');
  const textAnswerContent = await assistantAnswers.last().innerText();
  
  // Citations are usually in a ul below the assistant-markdown, in the same parent.
  const citationBlock = assistantAnswers.last().locator('xpath=following-sibling::div[contains(., "Citations:")]');
  await expect(citationBlock).toBeVisible();
  const textCitations = await citationBlock.innerText();

  // 5. Evaluate Text Answer
  const textEval = await evaluateAnswer(
    textQuestion,
    "Project codename is Aster Notes, and Backup format is portable JSON bundle.",
    textAnswerContent,
    textCitations
  );

  expect(textEval.passed).toBe(true);
  expect(textEval.correctness_score).toBeGreaterThanOrEqual(0.8);
  expect(textEval.usefulness_score).toBeGreaterThanOrEqual(0.75);
  expect(textEval.groundedness_score).toBeGreaterThanOrEqual(0.8);

  // 6. Ask a question about the PDF
  const pdfQuestion = 'What are the required citation behavior and success metric for RAG evaluation?';
  await page.fill('input[placeholder="Ask a question..."]', pdfQuestion);
  await page.click('button:has-text("Send")');

  await expect(page.locator('button[type="submit"]', { hasText: 'Sending...' })).toHaveCount(0, { timeout: 60000 });
  
  const pdfAnswerContent = await assistantAnswers.last().innerText();
  const pdfCitationBlock = assistantAnswers.last().locator('xpath=following-sibling::div[contains(., "Citations:")]');
  await expect(pdfCitationBlock).toBeVisible();
  const pdfCitations = await pdfCitationBlock.innerText();

  // 7. Evaluate PDF Answer
  const pdfEval = await evaluateAnswer(
    pdfQuestion,
    "Required citation behavior is that answers must cite source chunks. Success metric is grounded, concise, and useful response.",
    pdfAnswerContent,
    pdfCitations
  );

  expect(pdfEval.passed).toBe(true);
  expect(pdfEval.correctness_score).toBeGreaterThanOrEqual(0.8);
  expect(pdfEval.usefulness_score).toBeGreaterThanOrEqual(0.75);
  expect(pdfEval.groundedness_score).toBeGreaterThanOrEqual(0.8);

});

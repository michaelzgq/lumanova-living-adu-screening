# NotebookLM In This Screening Workflow

NotebookLM is **not** the live customer-facing chatbot here.

In this workflow, NotebookLM sits behind the scenes as an internal research and policy workspace:

1. You load official ADU, garage conversion, UDU, code, and housing-policy documents into NotebookLM.
2. You use NotebookLM to summarize updates, compare jurisdiction rules, and draft internal playbook notes.
3. You manually convert those notes into:
   - intake questions
   - blocker rules
   - city playbook pages
   - FAQ snippets
4. This Streamlit app uses those cleaned rules and notes to route customer leads.

## The closed loop

`Official documents -> NotebookLM internal research -> cleaned playbook + routing rules -> customer-facing chatbot -> saved lead -> paid screening`

## Why this matters

- NotebookLM is excellent for internal synthesis.
- Your front-end intake must still be deterministic and lead-focused.
- Customers should receive a preliminary routing result, not a final legal or permit opinion.

## What to update over time

- city-specific playbook entries
- blocker rules
- content snippets used in the chatbot
- risk-tier thresholds after real screening data comes in

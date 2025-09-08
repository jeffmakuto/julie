# Julie PreAuth Hybrid Agent (End-to-End)

**Overview**
This repository implements a hybrid pre-authorization assistant:
- **AWS (Bedrock + Textract + optional Kendra)** handle OCR, KB retrieval and LLM reasoning inside AWS.
- **Local LangChain-based orchestrator** runs on your server and acts as the agent brain — it calls AWS tools as "tools".

**Capabilities**
- Accepts inbound emails and attachments (PDF/photos/scans).
- Robust OCR pipeline (Textract + Rekognition fallback + local image processing hooks).
- Normalizes currencies and amounts (including words like "twelve thousand shillings").
- Extracts the following structured schema from email + attachments (always returns valid JSON):
  - `member_number` (string, mandatory; "unknown" if missing)
  - `member_name` (string, mandatory; "unknown" if missing)
  - `scheme_name` (string|null)
  - `claim_details` (array of {item,cost})
  - `invoiced_amount` (number)
  - `service_type` (string)
  - `clinical_summary` (string|null)
- Uses LLM (Bedrock model) to robustly parse messy text into structured output (JSON).
- Local LangChain agent orchestrates tools, applies business rules, and sends decision to RPA webhook.


# 🧩 High-Level Architecture

## 🎯 Goal
Automatically transform standard financial reports (CSV / Xero API) → semantic classification → alignment with accounting codes and segments (from `ACFR Definitions.xlsx`) → generation of import-ready templates (`9635_Import_Template_HC (2).xlsx`’s Template structure).  
The system can either export CSV/Excel or write back directly to Xero. [In progress: current phase focuses on Xero API + predefined QFR categories]

---

## ⚙️ Components

### 1. Connectors
- **Xero API Puller (code)**  
  OAuth login and P&L / Bills / Invoices pull are implemented, supports full-year ranges. Payroll endpoint is wired but Demo Company is unauthorized. [Partially done]

- **CSV Intake (code)**  
  CSV ingestion and schema normalization are not implemented yet. [Not done]

---

### 2. Reference Catalog (Co-Design)
- Built from `ACFR Definitions.xlsx` to define **allowed value dictionaries**, including:  
  - `GL / Account Code`, `Account Name` (from sheets like `AP (I&E)` and `AP (Balance Sheet)`)  
  - `Segment / Cost Center / Region` (e.g., Tracking Option Name 1/2)  
  For now, `category_definitions.json` is used as a transitional definition; it will be replaced by the formal ACFR dictionary. [Partially done]

- **Constraint principle**: These values serve as *hard boundaries* for the LLM output — the agent cannot invent new accounts or segments.  
  Enforced in mapping logic using predefined categories. [Done]

---

### 3. Classifier Agent (LLM + Tools)
- **Input**: Descriptions, notes, vendor names, invoice line details, and historical examples.  
  Current inputs: contact / description / amount / account code / type. [Done]

- **Output**: Suggested `Account Code`, `Account Name`, `Tracking Option (Name 1/2)`, `Class`, `Type`, etc. (restricted to allowed values).  
  Current output: QFR category + confidence + reason; tracking fields are not implemented. [Partially done]

- **Available Tools**:  
  - `get_allowed_values()` not yet extracted as a standalone tool; currently loaded within the flow. [Not done]  
  - `lookup_vendor_history(vendor)` uses a local mapping memory, but not formalized as vendor rules. [Partially done]  
  - `validate_mapping(candidate)` is not implemented with hard rejection yet. [Not done]

- **Logic and Boundaries**:  
  - Low-confidence → human review queue. [Done: HTML review list]  
  - High-confidence → proceed automatically. [Done]  
  - The agent only **suggests labels/routes** — it never performs calculations or accounting operations. [Done]

---

### 4. Rules Engine (code)
- **Priority logic**: amount thresholds, vendor whitelists/blacklists, fixed contracts, tax rates, project codes, etc. [Not done]  
- **Conflict resolution**: `Rules > Historical mapping > Agent suggestion`. [Not done]  
- **Auditability**: every decision is logged with who/what rule triggered it. [Not done]

---

### 5. Calculation & Validation (code)
- **Core features**:  
  - Tax-inclusive/exclusive conversions [Not done]  
  - Rounding strategies [Not done]  
  - Currency/date validation [Partially done: date range controls]  
  - Summation and reconciliation checks [Partially done: consistency test + Xero comparison]  
- **Deterministic implementation (no LLM)** to ensure reproducibility and traceability. [Partially done]  
- **Cross-check** with Xero’s tax rates and tracking categories. [Not done]

---

## 🔁 Overall Logic (Current, formal)
1. Complete OAuth authorization and bind the tenant to enable data access.  
2. Pull full-year Xero Profit & Loss and transaction lines (Bills / Invoices).  
3. Flatten line items and inject context (contact / description / account code / type).  
4. Classify into predefined QFR fields via AI and output confidence + reason.  
5. Generate detail, summary, income/expense split, and total tables.  
6. Pull Xero original P&L lines and compute differences.  
7. Generate visual report and human review list.  

---

## 🧠 Hard Parts / Constraints
- **Category alignment**: Xero P&L labels may not match QFR categories 1:1. [Risk]  
- **Payroll access**: Demo Company may not expose payroll endpoints. [Known limitation]  
- **Human-in-the-loop**: Low-confidence items need stronger review workflows. [Needs improvement]  
- **Mapping drift**: AI results can vary; memory cache helps, but governance is still required. [Long-term]  

Client Worksheet Generator (Excel ➜ Fillable PDF)

Generate a fillable PDF worksheet from a simple Excel file:
• Row 1 contains the client name.
• Each subsequent non-empty row contains a tax item line.
• The PDF renders one line item per tax row with: 1. Prompt text (Please upload your <tax item>), 2. A fillable text box (client can type notes / details), 3. A status choice with Uploaded and Not Needed (defaults unchecked).

Example: The attached screenshots show “Client Worksheet (2024)” with a client name at the top and a list of “Please upload your …” lines, each with a blank text field plus two checkboxes.

⸻

Why two checkboxes (vs radio buttons)?
• Two checkboxes support a natural tri-state:
• Uploaded (checked), Not Needed (checked), or Pending (both unchecked).
• Radios enforce mutual exclusivity but remove the easy “pending” state unless you add a third “Pending/None” radio, which increases visual clutter and can require a default.
• Recommendation: Keep two checkboxes for clarity and a clean pending state (both unchecked). If you later want mutual exclusivity, switch to a three-option radio group (Uploaded / Not Needed / Pending)—the code below supports either style via a config switch.

⸻

Inputs & Outputs

Excel input (minimal)
• A1 (or row 1): a cell containing Name of client: and the adjacent cell to the right with the actual name OR any cell on row 1 containing the name (we’ll detect).
• From row 4 down (by convention in your sheet) one non-empty cell per tax item (one item per line).

Robust parsing: we find the client name on row 1 (e.g., B1 in the screenshot) and collect all non-empty cells in the first populated column starting at row 4 as the items list.

PDF output
• Letter-sized, brand header (title + year + optional logo).
• Client name displayed below the header.
• For each item:
• Prompt text: Please upload your <item>.
• If the Excel text already starts with Please upload your, we use it verbatim.
• A fillable text field.
• Two checkboxes: “Uploaded” and “Not Needed” (unchecked).
• Automatic pagination with repeated column headings.

⸻

Architecture
• FastAPI on Cloud Run (single endpoint /generate).
• ReportLab to draw pages and create AcroForm fields (text fields, checkboxes or radios) dynamically.
• (Optional) pypdf only if you want to merge a branded background PDF; otherwise ReportLab draws the header band + logo.
• Google Identity Platform for login (Google + Email/Password).
• GCS to store PDFs and return a signed URL.

Different from the previous plan: We are generating a fresh form (dynamic fields) rather than filling a pre-made template with fixed field names.

⸻

Project Structure

client-worksheet/
app/
main.py # FastAPI routes (/ and /generate)
auth.py # Identity Platform token verify
excel.py # Parse name + items from Excel
pdf_build.py # Build dynamic fillable PDF with ReportLab
storage.py # GCS upload + signed URLs
static/
index.html # Login + simple upload UI
config/
layout.yaml # Margins, fonts, spacing, year, logo
options.yaml # choice style (checkbox|radio), labels
requirements.txt
Dockerfile
README.md # this file

⸻

Config

config/layout.yaml

year_label: "Client Worksheet (2024)"
logo_path: "" # optional path baked into the container (leave blank to skip)
page_size: "LETTER"
margins:
left: 54 # points (0.75")
right: 54
top: 72 # 1.0"
bottom: 54
fonts:
base: "Helvetica"
bold: "Helvetica-Bold"
sizes:
title: 28
client_name: 16
item_text: 12
column_header: 12
row_layout:
row_height: 56
item_text_width: 380
textfield_width: 380
textfield_height: 24
gap_x: 16
columns:
uploaded_label: "Uploaded"
not_needed_label: "Not Needed"
checkbox_size: 16

config/options.yaml

choice_style: "checkbox" # "checkbox" | "radio"
radio_values: # only used if choice_style = radio
uploaded: "uploaded"
not_needed: "not_needed"
prefix_mode: "auto" # "auto" | "verbatim"
auto_prefix: "Please upload your "

⸻

Data Flow 1. Auth (Google or Email/Password) → browser gets ID token. 2. Upload Excel to /generate with Authorization: Bearer <token>. 3. Server:
• Parse client name + list of items.
• Build PDF:
• Draw header (title + year + logo).
• Print client name.
• Render table header: Uploaded | Not Needed.
• For each item:
• Compute prompt text (auto prefix if needed).
• Add AcroForm text field for notes.
• Add two checkboxes OR a radio group (configurable).
• Flow to next page when space runs out (repeat header + column labels).
• Upload PDF to GCS (worksheets/<client>\_<date>.pdf).
• Return a signed URL.

We do not flatten the PDF (so the client can type & click). If you ever want to flatten returned forms, expose another endpoint to accept uploaded completed PDFs and flatten them via qpdf.

⸻

API
• GET / → login + upload UI.
• POST /generate
Headers: Authorization: Bearer <ID_TOKEN>
Body: multipart/form-data: file (xlsx/csv), optional job_name
Response:

{ "ok": true, "download_url": "<signed-url>", "page_count": 1, "items": 22 }

⸻

Implementation Notes

Excel parsing (excel.py)
• Find client name on row 1:
• Look for a cell with Name of client and take the next non-empty cell in that row,
• or fall back to the right-most non-empty cell in row 1.
• Detect the first non-empty column starting at row 4; read all non-empty cells until the first entirely empty gap of N rows (e.g., 3 in a row) or end of sheet.
• Normalize whitespace; keep original punctuation.

PDF builder (pdf*build.py)
• Use reportlab.pdfgen.canvas.Canvas with letter (or from config).
• Draw the purple header band + year title; place logo if provided.
• Print client name in bold beneath the header.
• Draw column labels Uploaded and Not Needed at fixed right-side x positions.
• Keep a cursor_y and decrement by row_height each item; when cursor_y crosses bottom, start a new page and redraw the header/column labels.
• Fields per row (unique names):
• Notes text field: note*{i}
• Checkboxes: uploaded*{i}, notneeded*{i}
• If radios: two radio widgets with the same name status\_{i} and different export values (e.g., uploaded, not_needed).
• Leave all fields empty/unchecked. Save PDF bytes to memory.

ReportLab field calls (reference):

form = c.acroForm

# text field

form.textfield(name=f"note\_{i}", x=x_tf, y=y_tf,
width=tf_w, height=tf_h, borderStyle='inset',
forceBorder=True, textColor=None)

# checkbox

form.checkbox(name=f"uploaded*{i}", x=x_up, y=y_chk, size=chk_sz)
form.checkbox(name=f"notneeded*{i}", x=x_nn, y=y_chk, size=chk_sz)

# radio (mutually exclusive)

form.radio(name=f"status*{i}", value="uploaded", x=x_up, y=y_chk, selected=False, size=chk_sz)
form.radio(name=f"status*{i}", value="not_needed", x=x_nn, y=y_chk, selected=False, size=chk_sz)

⸻

Security & Compliance
• Cloud Run service account has GCS write & sign permissions.
• Bucket is private; return signed URL with 1–24h TTL.
• No PII in logs (log only counts + job id).
• Lifecycle rule: auto-delete worksheets/\* after N days.

⸻

Requirements

fastapi
uvicorn[standard]
reportlab
pandas
openpyxl
google-cloud-storage
firebase-admin

(We no longer require pypdf or qpdf for MVP since we’re generating an interactive form, not flattening.)

# Run locally

uv run uvicorn app.main:app --reload

⸻

Deploy (Cloud Run)

PROJECT=YOUR_PROJECT
REGION=us-central1
SERVICE=client-worksheet
BUCKET=tax-worksheets

gcloud config set project $PROJECT
gsutil mb -p $PROJECT -l $REGION gs://$BUCKET || true
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com identitytoolkit.googleapis.com

gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT/apps/$SERVICE
gcloud run deploy $SERVICE \
  --image $REGION-docker.pkg.dev/$PROJECT/apps/$SERVICE \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars OUTPUT_BUCKET=$BUCKET \
 --memory 1Gi --cpu 1 --max-instances 3

⸻

Cursor Tasks for GPT-5 Agent (Do in order) 1. Scaffold repo per structure above; create requirements.txt, Dockerfile, configs. 2. Auth: Implement auth.py with Identity Platform token verify (firebase*admin.auth.verify_id_token). Add optional domain allowlist. 3. Excel parser: Implement excel.py:
• get_client_name_and_items(path) -> (name: str, items: list[str]) with robust detection described above. 4. PDF builder: Implement pdf_build.py:
• build_pdf(name, items, layout_cfg, options_cfg) -> bytes
• Handle pagination, header, column labels, and dynamic AcroForm fields (checkbox or radio group). 5. Storage: Implement storage.py (upload_bytes, signed_url). 6. API: Implement main.py:
• GET / serves static/index.html.
• POST /generate (auth required):
• Parse Excel, build PDF bytes, write to worksheets/{client}*{timestamp}.pdf.
• Return {"ok": true, "download_url": "...", "items": N, "page_count": P}. 7. UI: static/index.html:
• Firebase Web SDK auth (Google + Email/Password).
• After login, show upload form; POST with bearer token; show link. 8. Testing:
• Create a test Excel like your screenshot (name in row 1, items from row 4).
• Verify layout, field interactivity (open in Preview/Acrobat), pagination, and signed link. 9. Docs: Add a short “Staff Instructions” section below.

⸻

Staff Instructions 1. Sign in (Google or Email/Password). 2. Upload the Excel file:
• Row 1: client name (e.g., Michael H McKay).
• Row 4+: one tax item per line (paste). 3. Click Generate → download the fillable PDF. 4. Send to client. (They can type notes and check Uploaded/Not Needed per item.)

⸻

Future Options
• Mutual exclusivity: switch choice_style: radio (two radios per row) or add a third Pending radio to retain tri-state.
• Brand template: use a background PDF (company stationery) and draw on top.
• Bulk mode: accept a workbook with multiple clients (one sheet per client).
• Return/flatten: add endpoint to accept a completed PDF and produce a flattened archive copy.

⸻

## Staff Instructions

1. Sign in (Google or Email/Password).
2. Upload the Excel file (Row 1 contains the client name, row 4+ include document prompts).
3. Click Generate to produce the fillable PDF.
4. Download and send to the client for completion.

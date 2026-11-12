# Scrutiny checklist, inspection report and email templates

Office context (confirm with the user if anything has changed):
- Officer: **Vishnu N, Assistant, Employee Code 2173, Spices Board, Regional Office (Marketing), Bengaluru**.
- Office for tour programmes: IIPM, Jnana Bharathi Campus, Malathahalli, Outer Ring Road, Bengaluru.
- Controlling officer for emails: **Mr. N. Sundaresan, Dy. Director** – `sundaresan.n@spicesboard.gov.in`.
- Administrator who assigns/receives files on DGFT: **reji k, Administrator**.
- Gmail used: the office account connected through the Gmail connector. Look at earlier *sent* mail for wording before drafting.

## A. Document scrutiny (before inspection)

Crucial documents for a manufacturing unit – every one must be present and in proper shape:

| Document | What to check |
|---|---|
| **FSSAI Central Licence** | Valid date; **"Manufacturer – Exporter"** kind of business present; product annexure covers the spices to be exported (12.2 herbs/spices etc.); manufacturing vs repacker items; capacity (MT/day); authorised premises address = unit address |
| **Pollution Control Board consent (CFO)** | Valid (not expired); in the firm's name; products include spice processing (not only other products); address/survey numbers match |
| **Udyam / MSME** | NIC **10795 – Grinding and processing of spices** present; unit address |
| **Land / ownership** | Sale deed / registered lease / recent property tax receipt **in the firm's name**. Red flags: only a telephone/electricity bill; old company name (needs name-change certificate + notarised affidavit); lease on wrong stamp article (e.g. residential ≤1 year for a 5-year industrial lease), unregistered/unwitnessed; no lessor ownership proof |
| **Bank Confidential Report (Annexure II)** | On the **bank's own letterhead**, recent date, Annex-II 14 fields, options actually selected (not "GOOD/SATISFACTORY/UNSATISFACTORY" left as is), signed + sealed, **account number matches the application** |
| **GST certificate** | Principal place of business / additional place = unit address |
| **IEC** | Name and address match |

Also: address uniformity across all documents (survey numbers, PIN code), names of partners/directors, whether the application's export product list matches what FSSAI and PCB allow. Compare installed capacity across FSSAI and PCB (FSSAI MT/day is normally the figure to quote).

Report findings as tables: document → what it shows → ✅/⚠️/❌. Then recommend either inspection or "mark deficient" with a remark (≤200 characters, capitals, e.g. `PL UPLOAD 1) ... 2) ... 3) ...`). Never mark deficient, approve, reject or send without the user's explicit go-ahead.

Unit far from Bengaluru (e.g. Karwar, Mangaluru/Bantwal) → draft an email to Mr. Sundaresan to depute a nearby official (template C1).

## B. Inspection report

Template: `assets/inspection_report_format.docx` (Spices Board 2021 format). Fill it with `scripts/fill_report.py <template> <values.json> <out.docx>`. The JSON maps row numbers (0–32) to lists of lines; omitted rows keep the template text. Row map:

| Row | Item | Row | Item |
|---|---|---|---|
| 0 | 1 Name & address (firm, factory, regd office) | 17 | 15 Machinery – keep "Attach separate sheet (Annex I)" |
| 1 | 2 IEC / File No. | 18 | 16 Drying yard |
| 2 | 3 Date of submission | 19 | 17 Potable water |
| 3 | 4 New / Renewal / Amendment | 20 | 18 Separate storage |
| 4 | 4a Previous CRES (type, number, issue date, validity) | 21 | 19a Quality lab |
| 5 | 5 Unit location | 22 | 19b Testing arrangement |
| 6 | 6 Date of inspection | 23 | 20 Effluent & waste management |
| 7 | 7 Owned / leased (with document details) | 24 | 21 Production & export, last 3 years |
| 8 | 8 Investment (Land / Machinery in lakhs) | 25 | 22 Overall hygiene |
| 9 | 9 Employees / Supervisors / Others | 26 | 23 Defects noticed |
| 10 | 10 CEO / Production Mgr / QC Mgr (first line blank) | 27 | 24 In operation? |
| 11 | 11 ISO / HACCP / GMP | 28 | 25 Person discussed with |
| 12 | 12 FSSAI registration | 29 | 26 Other details (self-sealing, plant quarantine, trademark…) |
| 13 | 11 FSSAI licence no. & date | 30 | 27 Recommended? |
| 14 | 12 PCB consent details | 31 | 27a Reasons if not |
| 15 | 13 Spices processed & technology | 32 | 28 Officer name / designation / employee code / office |
| 16 | 14 Installed capacity | | |

Get the officer's answers for everything seen at the unit (staff counts, key people, investment, drying yard, water, storage, lab, operation, hygiene, defects, recommendation). Fill document facts yourself from the scrutiny. Leave a blank or "YES / NO" for anything not given and list those to the user – do not guess. Precedents the user accepted:
- Re-application after expiry → **NEW** (old CRES listed in 4a).
- Merchant → Manufacturer change → **AMENDMENT**.
- Dry-grinding units: potable water "processes only powdered items… water not required for processing"; effluent "Not applicable – dry process; domestic effluent only as per KSPCB consent".
- No in-house lab → "NO"; 19b "Samples are sent to external NABL-accredited laboratories for testing."
- No exports → Production/Export "Nil" for each of the 3 years (ask about production if turnover is large).

Convert: `soffice --headless --convert-to pdf report.docx`, render with `pdftoppm` and look at every page. Aim for 3 pages (`--font-size 9` if it spills).

## C. Final PDF pack for DGFT upload (must be < 5 MB)

Order the user wants: **Inspection report (signed) → photographs → machinery list → any other enclosures they name** (e.g. water test report, certifications, declarations, payroll).

- Signed sheet as a phone photo: `scripts/scan_page.py photo.jpg out.jpg [x1,y1,x2,y2,x3,y3,x4,y4]` (corners TL,TR,BR,BL in pixels; auto-detect often fails on glass tables – draw a grid, read the corners, pass them).
- Signature image: `scripts/build_pack.py --signature sig.jpg` stamps it under item 28 on the last report page with "VISHNU N / ASSISTANT / SPICES BOARD, BENGALURU".
- Photos: 2 per A4 page with a heading "PHOTOGRAPHS TAKEN DURING UNIT INSPECTION" + firm, address, date. Exclude photos of handwritten notes.
- Rotate sideways scans upright; recompress big scans (JPEG ~110–120 dpi, quality 60–70).
- Check the total size and look at a contact sheet of all pages before sending.

## D. DGFT steps after the report is final (each needs the user's OK)
1. Attachments → type **EPC Officer Added**, remark "INSPECTION REPORT WITH ENCLOSURES", upload PDF.
2. "Details to be printed in RCMC Certificate": list current vs proposed and wait for approval.
   - New registration: Membership Category **New Member**; Issue Date = date of processing (today); Valid Upto = issue date + 3 years − 1 day (user's rule: 27/10/2026 → 26/10/2029).
   - Amendment: Membership Category **Amendment**; keep the **existing RCMC's issue and expiry dates** (Basic Details → RCMC Details table) – the amendment does not extend validity.
   - Description of goods: always set to **SPICES AND SPICE PRODUCTS** (user's standing rule: uniform for all applications).
   - Remark for a file inspected by a deputed official: name them, e.g. `UNIT INSPECTED ON DD-MM-YYYY BY SHRI <NAME>, <DESIGNATION>, <OFFICE>. INSPECTION REPORT WITH ENCLOSURES UPLOADED. RECOMMENDED FOR ISSUE OF RCMC AS MANUFACTURER EXPORTER.`
   - Tick declaration → Save certificate details.
3. Send → **reji k,Administrator**, remark e.g. `UNIT INSPECTED ON DD-MM-YYYY. INSPECTION REPORT WITH ENCLOSURES UPLOADED. RECOMMENDED FOR ISSUE OF RCMC AS MANUFACTURER EXPORTER.` (or "…FOR AMENDMENT OF RCMC AS MANUFACTURER EXPORTER."). Verify in file history.

## E. Email templates (Gmail drafts only – never send)

Attachments larger than ~40 KB cannot be added reliably through the Gmail tool: create the draft, send the PDF to the user with SendUserFile and tell them to attach it.

### C1. Deputation of a nearby official
Subject: `Request to Depute an Official for Unit Inspection – M/s <FIRM>, <PLACE>`
```
Respected Sir,

We have received an application for issue of RCMC from M/s <FIRM> (File No. <FILE>). However, the unit is located at <UNIT ADDRESS>.

We kindly request you to depute an official from a nearby office to conduct the unit inspection.

The deputed official is requested to collect the following documents and submit the inspection report, along with these documents and the recommendation:

1. MSME/Udyam/Udyog Aadhaar Registration Certificate (Code 10795 – Grinding and Processing of Spices).
2. FSSAI Licence (State/Central, as applicable) along with Product Annexure/Form C covering spices and spice products.
3. Proof of ownership/lease of the premises.
4. List of machinery installed in the unit.
5. Water Test Report (if potable water is being used in the processing activities).
6. Self-Sealing and Self-Stuffing Permission issued by Customs.
7. Details and copies of certifications, if available, such as ISO, HACCP, HALAL, KOSHER, NPOP/NSOP, etc.
8. Copy of the Consent/Authorization issued by the State Pollution Control Board concerned.

The inspection report, documents and recommendation will then be uploaded in the DGFT portal and the RCMC will be issued accordingly.

A copy of the application is attached for reference.

Regards,
Vishnu N
Assistant
Spices Board, Regional Office, Bengaluru
```

### C2. Inspection report uploaded (for information)
Subject: `Inspection Report – M/s <FIRM>, <PLACE> – Uploaded in DGFT Portal`
```
Respected Sir,

The manufacturing unit inspection of M/s <FIRM>, <UNIT ADDRESS> (File No. <FILE>) was conducted on <DD-MM-YYYY>.

The inspection report has been uploaded in the DGFT portal for <issuance of RCMC as Manufacturer Exporter | amendment of RCMC No. <NO> from Merchant Exporter to Manufacturer Exporter>.

The documents uploaded in the portal are enclosed for your kind reference, in the following order:

1. Inspection Report
2. ... (list exactly what is in the PDF, in order)

Submitted for your kind information.

Regards,
Vishnu N
Assistant
Spices Board, Regional Office, Bengaluru
```

### C3. Advance Tour Program (ATP)
Subject: `Advance Tour Program (ATP) – Vishnu N – DD.MM.YYYY`. Copy the HTML table from the latest sent ATP (search `in:sent subject:"Advance Tour Program"`): bilingual headers Departure (Place, Date & Time) / Arrival (Place, Date & Time) / Purpose of Journey / Mode of Journey / Total Kilometers. Purpose names the firm, full unit address, and the RCMC purpose with file/RCMC numbers. Ask the user for date, start/return times and mode. Distance: road route from the office (OpenStreetMap Nominatim + OSRM `router.project-osrm.org/route/v1/driving/lon,lat;lon,lat`), round trip, **+2 km buffer**, written "NN Kms (approx.)". Sign-off:
```
Submitted for kind approval.

Regards,
Vishnu N
Employee Code: 2173
Spices Board, Regional Office (Marketing), Bengaluru
```

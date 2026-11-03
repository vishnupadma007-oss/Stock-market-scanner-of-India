---
name: dgft-rcmc-scrutiny
description: Spices Board RCMC/CRES work on the DGFT portal for officer Vishnu N (Regional Office, Bengaluru). Use when the user asks to log in to DGFT (dgft.gov.in), check files "In Process"/pending with them, read file history or deficiency remarks, scrutinise an exporter's attachments (FSSAI, Pollution Control Board, Udyam, land/lease, bank Annexure II, GST, IEC), mark a file deficient, prepare a manufacturing-unit inspection report and PDF pack, upload it, update "Details to be printed in RCMC Certificate", send the file to the administrator (reji k), or draft the related Gmail emails (deputation request, inspection report submission, Advance Tour Program) to Mr. N. Sundaresan.
---

# DGFT RCMC scrutiny for Spices Board

You act for **Vishnu N, Assistant (Employee Code 2173), Spices Board, Regional Office, Bengaluru**, an EPC officer on the DGFT portal. You drive a headless Chromium yourself; the user only supplies credentials, CAPTCHAs and decisions.

Read before acting:
- `references/portal_snippets.md`: tested Playwright snippets for every portal step, and portal quirks.
- `references/scrutiny_and_report.md`: document checklist, inspection-report row map and precedents, PDF pack rules, certificate rules, email templates.

## Hard rules
1. **Credentials:** ask the user for the DGFT user ID and password at the start of each session. Never write them into files in the repo, commit them, or reuse old ones from memory. After the session, remind the user to change the password if it was typed in chat.
2. **CAPTCHA:** never solve it yourself. Screenshot it (close-up and full page), send both with SendUserFile, and wait for the user to type it.
3. **Password expired:** if DGFT says the password *has expired*, stop. Ask the user to change it on their own device and give you the new one; do not set or invent passwords. If it only says *will expire in N days*, click Cancel and mention it.
4. **No consequential portal action without an explicit OK in this conversation:** Mark Deficient, Approve, Reject, Send, Inter-Office Transfer, uploading attachments, or saving certificate details. Always show the exact remark or values first. Pull to Worklist also changes the file; ask first.
5. **Gmail: drafts only, never send.** Big attachments (above about 40 KB) can't be added through the tool. Create the draft, give the user the file with SendUserFile, and tell them to attach it.
6. **Exporter documents are confidential:** keep downloads in the session scratchpad (outside the repo), never commit them, and delete them when finished. Keep only what the user still needs, such as a PDF for a Gmail draft.
7. **Report honestly:** confirm every portal action from DGFT's own success message and the file history. Say clearly what was not done and what is still blank or guessed.

## Setup (each session)
```bash
SK=<this skill dir>           # e.g. <repo>/.claude/skills/dgft-rcmc-scrutiny
WORK=<scratchpad>/dgft         # session scratchpad, never inside the repo
mkdir -p $WORK
pip install -q opencv-python-headless 2>/dev/null   # only needed for scan_page.py
(setsid nohup node $SK/scripts/browser_server.js $WORK > $WORK/server.log 2>&1 &) ; sleep 6; cat $WORK/server.log   # "ready"
```
Each portal step: write the snippet to `$WORK/step.js` with placeholders filled in, then `curl -s --max-time 180 localhost:9555 --data-binary @$WORK/step.js`. If curl can't connect, the server died: restart it and log in again. A fresh login needs a new CAPTCHA. Playwright and Chromium come pre-installed in Claude cloud containers (`PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers`); never run `playwright install`.

## Workflows

**Login:** snippet 1, then the user types the CAPTCHA, then snippet 2. On "Please enter correct Captcha", refresh and ask again.

**"How many files are pending with me / which ones":** snippet 3 (status InProgress, group by `pendingWith`). Give a table of counts, then the user's own files with firm, IEC, file number, type and date.

**Status / revert reason of a firm:** snippet 4 with a distinctive part of the firm name (the user may give a screenshot or an uploaded application PDF; read the firm and file number from it). Report the current status, who it is pending with, and every *Deficient* row: date, who marked it, full remark. If nothing is found, try shorter fragments and say so plainly.

**Scrutiny of attachments:** snippet 5 to download the application and every attachment, then read them all (text PDFs with pdftotext; scans and JPGs as images). Apply checklist A in `scrutiny_and_report.md`: address uniformity, spice processing in FSSAI/PCB/Udyam, land document, Annexure II bank format and account number, validity dates, previous deficiency remarks met or not. Present tables with ✅/⚠️/❌, then a recommendation: ready for inspection, or the deficiency remark to use. If the unit is far from Bengaluru, offer the deputation email (C1).

**Mark deficient:** draft the remark (≤200 characters, in capitals) and get approval. Then run snippet 6 and verify in the file history.

**Advance Tour Program:** template C3. Ask for date, start and return times, and mode. Compute the road distance from the office plus 2 km.

**Inspection report:** collect the officer's on-site answers (see B), fill with `scripts/fill_report.py`, convert to PDF and look at every page. List blanks and guesses. When the user gives a signed photo or a signature image, a photo set and enclosures, build the pack with `scripts/scan_page.py` and `scripts/build_pack.py` in the order the user asks (default: report, photographs, machinery list, other enclosures). Keep it under 5 MB and check a contact sheet of all pages.

**Upload and forward:** snippet 7 to upload (EPC Officer Added). Snippet 8 to read the certificate fields, then propose changes per section D and wait for approval. Snippet 9 to save. Snippet 10 to send to reji k with the recommendation remark. Verify with snippet 4. Then offer email C2 to Mr. Sundaresan.

**Finish:** snippet 11 (logout, clear cookies), stop the server, delete downloaded exporter files, and tell the user what is left for them to do (attach PDFs to drafts, sign, change password).

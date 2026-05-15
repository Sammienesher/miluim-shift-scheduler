# Deploy: Personal Itinerary Sidebar

## Files

| File | Purpose |
|---|---|
| `Code.gs` | Server-side logic (menu, data, email) |
| `Sidebar.html` | Client-side sidebar UI |
| `appsscript.json` | Manifest (scopes, timezone, runtime) |

---

## Steps

### 1. Open the spreadsheet

Open: `https://docs.google.com/spreadsheets/d/1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI`

---

### 2. Open Apps Script editor

**Extensions → Apps Script**

A new tab opens with the script editor.

---

### 3. Set up Code.gs

1. In the editor, click on `Code.gs` (left sidebar under "Files")
2. **Select all** the default content and **delete** it
3. Paste the entire contents of `Code.gs` from this repo
4. Press **Ctrl+S** (or ⌘S) to save

---

### 4. Create Sidebar.html

1. Click the **+** button next to "Files" in the left sidebar
2. Choose **HTML**
3. Name it exactly: `Sidebar` (no `.html` extension — Apps Script adds it)
4. Delete the default content
5. Paste the entire contents of `Sidebar.html` from this repo
6. Press **Ctrl+S** to save

---

### 5. Set the manifest (appsscript.json)

> The manifest is hidden by default. Reveal it:

1. Click **Project Settings** (gear icon ⚙️, bottom-left)
2. Check **"Show 'appsscript.json' manifest file in editor"**
3. Go back to the Editor
4. Click `appsscript.json` in the file list
5. Replace its contents with the contents of `appsscript.json` from this repo
6. Save

---

### 6. Name the project

1. Click **"Untitled project"** at the top
2. Rename it to: `Miluim Personal Itinerary`
3. Click **Rename**

---

### 7. Authorize

1. Click **Run** → select function `onOpen` from the dropdown
2. Click ▶ Run
3. A popup asks for authorization → click **Review permissions**
4. Choose your Google account
5. Click **Advanced** → **Go to Miluim Personal Itinerary (unsafe)**
6. Click **Allow**

> This grants the script access to Sheets, Gmail, and the UI.

---

### 8. Refresh the spreadsheet

Go back to the spreadsheet tab and **refresh the page** (F5).

After reload, a new menu **"שליח/י"** appears in the menu bar.

---

### 9. Open the sidebar

**שליח/י → לוח משמרות אישי**

The sidebar opens on the right side.

---

### 10. Use it

1. **בחר/י שם** — pick a person from the dropdown (loads from the `groups` tab)
2. Set **תאריך התחלה** and **תאריך סיום** (defaults: 06/05/26 – 08/07/26)
3. Click **הצג לוח משמרות**
4. View the shift table with morning/night badges
5. Click **📧 שלח/י לי את הלוח באימייל** to receive an `.ics` calendar file

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Menu doesn't appear after refresh | Run `onOpen` manually from the editor |
| "Authorization required" on first sidebar open | Re-run `onOpen` from editor to trigger auth flow |
| Empty dropdown in sidebar | Check that `groups` sheet has data in rows 2-15, cols A-F |
| No shifts found | Verify schedule sheet name matches `משמרות הערכה ועיבוד` exactly |
| Email not received | Check spam; verify email address in `groups` col B/E |

---

## Sheet Layout Expected

### `groups` tab
| Col A | Col B | Col C | Col D | Col E | Col F |
|---|---|---|---|---|---|
| שם (צוות 1) | אימייל | תפקיד | שם (צוות 2) | אימייל | תפקיד |
| Row 1 = header, rows 2-15 = people |

### `משמרות הערכה ועיבוד` tab
| Row | Content |
|---|---|
| 3 | Date headers (e.g. `Monday, 01/06/26`) — team 1, from col B |
| 4 | Morning names — team 1 |
| 5 | Night names — team 1 |
| 8 | Morning names — team 2 |
| 9 | Night names — team 2 |

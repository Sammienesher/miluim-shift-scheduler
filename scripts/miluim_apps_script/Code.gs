// ─── Constants ───────────────────────────────────────────────────────────────
const SHEET_ID    = '1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI';
const GROUPS_TAB  = 'groups';
const SCHEDULE_TAB = 'משמרות הערכה ועיבוד';
const SHIFT_1_NAME  = 'בוקר';
const SHIFT_2_NAME  = 'לילה';
const SHIFT_1_START = '06:00';
const SHIFT_1_END   = '18:00';
const SHIFT_2_START = '18:00';
const SHIFT_2_END   = '06:00';

// ─── Menu ────────────────────────────────────────────────────────────────────
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('משמרות')
    .addItem('לוח אישי', 'showSidebar')
    .addItem('החלפת משמרת', 'showSwapSidebar')
    .addToUi();
}

// ─── Swap Sidebar ─────────────────────────────────────────────────────────────
function showSwapSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('SwapSidebar')
    .setTitle('החלפת משמרת')
    .setWidth(380);
  SpreadsheetApp.getUi().showSidebar(html);
}

// Get all shifts with team info for a person (used by swap sidebar)
function getMyShiftsWithTeam(personName) {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sheet = ss.getSheetByName(SCHEDULE_TAB);
  const normName = norm(personName);
  const numCols = 60;
  
  // R3=headers, R4=team1 morn, R5=team1 night, R8=team2 morn, R9=team2 night
  const headers  = sheet.getRange(3, 2, 1, numCols).getValues()[0];
  const t1m = sheet.getRange(4, 2, 1, numCols).getValues()[0];
  const t1n = sheet.getRange(5, 2, 1, numCols).getValues()[0];
  const t2m = sheet.getRange(8, 2, 1, numCols).getValues()[0];
  const t2n = sheet.getRange(9, 2, 1, numCols).getValues()[0];
  
  const dateRegex = /(\d{2})\/(\d{2})\/(\d{2})/;
  const results = [];
  
  const configs = [
    { row: t1m, team: 'הערכה', type: 'בוקר' },
    { row: t1n, team: 'הערכה', type: 'לילה' },
    { row: t2m, team: 'עיבוד', type: 'בוקר' },
    { row: t2n, team: 'עיבוד', type: 'לילה' },
  ];
  
  for (let i = 0; i < numCols; i++) {
    const header = String(headers[i] || '');
    const match = header.match(dateRegex);
    if (!match) continue;
    
    const dateStr = match[1] + '/' + match[2] + '/20' + match[3];
    const isoDate = ddmmyyToISO(match[1], match[2], match[3]);
    
    // Only future dates
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const shiftDate = new Date(isoDate + 'T12:00:00');
    if (shiftDate < today) continue;
    
    for (const cfg of configs) {
      if (norm(cfg.row[i]) === normName) {
        results.push({
          date: isoDate,
          dateStr: dateStr,
          dayName: getDayNameHebrew(shiftDate),
          shiftType: cfg.type,
          team: cfg.team,
        });
      }
    }
  }
  
  results.sort((a, b) => a.date < b.date ? -1 : a.date > b.date ? 1 : 0);
  return results;
}

// Get all people's names for the dropdown
function getPeopleNames() {
  const people = getPeople();
  return people.map(p => p.name);
}

// Submit a swap request to the staging area
function submitSwapRequest(personName, shiftDate, shiftType, team) {
  try {
    const ss = SpreadsheetApp.openById(SHEET_ID);
    let swapSheet = ss.getSheetByName('Swaps');
    if (!swapSheet) {
      swapSheet = ss.insertSheet('Swaps');
      swapSheet.getRange(1, 1, 1, 7).setValues([[
        'תאריך בקשה', 'שם', 'תאריך משמרת', 'סוג', 'צוות', 'סטטוס', 'תוצאה'
      ]]);
      swapSheet.setFrozenRows(1);
    }
    
    // Find next empty row
    const lastRow = swapSheet.getLastRow() + 1;
    const now = new Date();
    const timestamp = Utilities.formatDate(now, 'Asia/Jerusalem', 'dd/MM/yy HH:mm');
    
    swapSheet.getRange(lastRow, 1, 1, 6).setValues([[
      timestamp, personName, shiftDate, shiftType, team, 'ממתין'
    ]]);
    
    return { success: true, row: lastRow };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

// ─── Personal Itinerary Sidebar ──────────────────────────────────────────────
function showSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('לוח משמרות אישי')
    .setWidth(340);
  SpreadsheetApp.getUi().showSidebar(html);
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function norm(s) {
  if (!s) return '';
  return String(s)
    .trim()
    .replace(/\u2019/g, "'")
    .replace(/\u2018/g, "'")
    .replace(/\u05f3/g, "'")
    .replace(/\s+/g, ' ');
}

function getDayNameHebrew(dateObj) {
  const days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'];
  return days[dateObj.getDay()];
}

// Pad a number to 2 digits
function pad2(n) { return String(n).padStart(2, '0'); }

// Convert DD/MM/YY → YYYY-MM-DD
function ddmmyyToISO(dd, mm, yy) {
  const year = parseInt(yy, 10) + 2000;
  return year + '-' + pad2(parseInt(mm, 10)) + '-' + pad2(parseInt(dd, 10));
}

// ─── getPeople ───────────────────────────────────────────────────────────────
function getPeople() {
  const ss     = SpreadsheetApp.openById(SHEET_ID);
  const sheet  = ss.getSheetByName(GROUPS_TAB);
  // Rows 2-15 (skip header row 1), cols A-F (1-6)
  const data   = sheet.getRange(2, 1, 14, 6).getValues();
  const people = [];

  data.forEach(function(row) {
    // Team 1: cols A(0), B(1), C(2) → name, email, role
    const name1 = norm(row[0]);
    if (name1) {
      people.push({ name: name1, email: String(row[1]).trim(), team: 'צוות 1' });
    }
    // Team 2: cols D(3), E(4), F(5) → name, email, role
    const name2 = norm(row[3]);
    if (name2) {
      people.push({ name: name2, email: String(row[4]).trim(), team: 'צוות 2' });
    }
  });

  return people;
}

// ─── getShifts ────────────────────────────────────────────────────────────────
// personName: string, startDate: "YYYY-MM-DD", endDate: "YYYY-MM-DD"
function getShifts(personName, startDate, endDate) {
  const ss      = SpreadsheetApp.openById(SHEET_ID);
  const sheet   = ss.getSheetByName(SCHEDULE_TAB);
  const normName = norm(personName);

  // Read rows 3-9 (GSheets rows 3..9), starting from col B (col 2)
  // We need enough columns — grab 60 to cover the full date range
  const numCols = 60;
  // Row 3 = date headers team1, Row 4 = shift1 team1, Row 5 = shift2 team1
  // Row 8 = shift1 team2,        Row 9 = shift2 team2
  const headerRow  = sheet.getRange(3, 2, 1, numCols).getValues()[0]; // date headers
  const t1shift1   = sheet.getRange(4, 2, 1, numCols).getValues()[0]; // team1 morning
  const t1shift2   = sheet.getRange(5, 2, 1, numCols).getValues()[0]; // team1 night
  const t2shift1   = sheet.getRange(8, 2, 1, numCols).getValues()[0]; // team2 morning
  const t2shift2   = sheet.getRange(9, 2, 1, numCols).getValues()[0]; // team2 night

  const dateRegex = /(\d{2})\/(\d{2})\/(\d{2})/;
  const results   = [];

  for (let i = 0; i < numCols; i++) {
    const header = String(headerRow[i]);
    const match  = header.match(dateRegex);
    if (!match) continue;

    const isoDate = ddmmyyToISO(match[1], match[2], match[3]);
    if (isoDate < startDate || isoDate > endDate) continue;

    const dateObj  = new Date(isoDate + 'T12:00:00');
    const dayName  = getDayNameHebrew(dateObj);

    // Check morning (rows t1shift1, t2shift1)
    const morningNames = [norm(t1shift1[i]), norm(t2shift1[i])];
    if (morningNames.some(function(n) { return n === normName; })) {
      results.push({ date: isoDate, dayName: dayName, shiftType: SHIFT_1_NAME });
    }

    // Check night (rows t1shift2, t2shift2)
    const nightNames = [norm(t1shift2[i]), norm(t2shift2[i])];
    if (nightNames.some(function(n) { return n === normName; })) {
      results.push({ date: isoDate, dayName: dayName, shiftType: SHIFT_2_NAME });
    }
  }

  results.sort(function(a, b) { return a.date < b.date ? -1 : a.date > b.date ? 1 : 0; });
  return results;
}

// ─── emailItinerary ───────────────────────────────────────────────────────────
function emailItinerary(personName, startDateStr, endDateStr) {
  try {
    const shifts = getShifts(personName, startDateStr, endDateStr);

    // Find email for this person
    const people = getPeople();
    const person = people.find(function(p) { return norm(p.name) === norm(personName); });
    if (!person || !person.email) {
      return { success: false, error: 'לא נמצאה כתובת אימייל עבור ' + personName };
    }

    if (shifts.length === 0) {
      return { success: false, error: 'לא נמצאו משמרות בטווח התאריכים הנבחר' };
    }

    const tz = Session.getScriptTimeZone(); // "Asia/Jerusalem"
    const icsLines = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//Miluim Schedule//EN',
      'CALSCALE:GREGORIAN',
      'METHOD:PUBLISH',
      'X-WR-CALNAME:לוח משמרות - ' + personName,
      'X-WR-TIMEZONE:' + tz,
    ];

    shifts.forEach(function(shift) {
      // Parse date parts
      const parts = shift.date.split('-');
      const yr  = parts[0];
      const mo  = parts[1];
      const dy  = parts[2];

      let dtStart, dtEnd, summaryText, descText;

      if (shift.shiftType === SHIFT_1_NAME) {
        // Morning: 06:00-18:00 same day
        dtStart   = yr + mo + dy + 'T060000';
        dtEnd     = yr + mo + dy + 'T180000';
        summaryText = 'משמרת בוקר - הערכה';
        descText    = 'משמרת בוקר\\n06:00-18:00';
      } else {
        // Night: 18:00 → 06:00 next day
        dtStart = yr + mo + dy + 'T180000';
        // Calculate next day
        const d = new Date(shift.date + 'T12:00:00');
        d.setDate(d.getDate() + 1);
        const nyr = String(d.getFullYear());
        const nmo = pad2(d.getMonth() + 1);
        const ndy = pad2(d.getDate());
        dtEnd       = nyr + nmo + ndy + 'T060000';
        summaryText = 'משמרת לילה - הערכה';
        descText    = 'משמרת לילה\\n18:00-06:00';
      }

      // Unique ID for deduplication
      const uid = 'miluim-' + personName.replace(/\s/g, '') + '-' + shift.date + '-' + shift.shiftType + '@miluim';

      icsLines.push('BEGIN:VEVENT');
      icsLines.push('UID:' + uid);
      icsLines.push('DTSTART;TZID=' + tz + ':' + dtStart);
      icsLines.push('DTEND;TZID='   + tz + ':' + dtEnd);
      icsLines.push('SUMMARY:'   + summaryText);
      icsLines.push('DESCRIPTION:' + descText);
      icsLines.push('END:VEVENT');
    });

    icsLines.push('END:VCALENDAR');
    const icsContent = icsLines.join('\r\n');

    const blob = Utilities.newBlob(icsContent, 'text/calendar', 'miluim-schedule.ics');

    const subject = 'לוח משמרות אישי - ' + personName;
    const body    = 'שלום ' + personName + ',\n\nמצורף לוח המשמרות שלך לתאריכים ' +
                    startDateStr + ' - ' + endDateStr + '.\n\n' +
                    'סה"כ ' + shifts.length + ' משמרות.\n\nבהצלחה!';

    GmailApp.sendEmail(person.email, subject, body, {
      attachments: [blob],
      name: 'מערכת לוח משמרות מילואים'
    });

    return { success: true, count: shifts.length };
  } catch (e) {
    return { success: false, error: e.message };
  }
}

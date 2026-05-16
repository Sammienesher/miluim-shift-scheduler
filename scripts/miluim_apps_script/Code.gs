// ═══════════════════════════════════════════════════════════════════
// EXISTING — Constraints coloring & dropdowns
// ═══════════════════════════════════════════════════════════════════

const VALUE_COLOR_MAP = {
  'יכול': '#afd095',
  'לא יכול': '#ff6d6d',
  'יכול רק בוקר': '#b4c7dc',
  'יכול רק לילה': '#bf819e',
  'לא ידוע': '#ffffa6',
};

const TEXT_COLOR_MAP = {
  'יכול': '#000000',
  'לא יכול': '#000000',
  'יכול רק בוקר': '#000000',
  'יכול רק לילה': '#000000',
  'לא ידוע': '#000000',
};

const SHEET_NAME = 'משמרות הערכה ועיבוד';
const DATA_START_ROW = 16;
const DATA_END_ROW = 28;
// Column F (col 6) is the counter column - must be excluded
const DATA_COLS = [2, 3, 4, 5, 7]; // B, C, D, E, G

function updateAllColors() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) { Logger.log('Sheet not found'); return; }
  for (const col of DATA_COLS) {
    const range = sheet.getRange(DATA_START_ROW, col, DATA_END_ROW - DATA_START_ROW + 1, 1);
    const values = range.getValues();
    const bgs = values.map(r => [VALUE_COLOR_MAP[r[0]] || null]);
    const fgs = values.map(r => [TEXT_COLOR_MAP[r[0]] || '#000000']);
    range.setBackgrounds(bgs);
    range.setFontColors(fgs);
  }
}

function applyDropdowns() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) return;
  const options = ['יכול', 'יכול רק בוקר', 'יכול רק לילה', 'לא ידוע', 'לא יכול'];
  const rule = SpreadsheetApp.newDataValidation()
    .requireValueInList(options, true)
    .setAllowInvalid(false)
    .build();
  sheet.getRange(DATA_START_ROW, 2, DATA_END_ROW - DATA_START_ROW + 1, 4).setDataValidation(rule);
  sheet.getRange(DATA_START_ROW, 7, DATA_END_ROW - DATA_START_ROW + 1, 1).setDataValidation(rule);
}

function onEdit(e) {
  const sheet = e.source.getActiveSheet();
  if (sheet.getName() !== SHEET_NAME) return;
  const range = e.range;
  const row = range.getRow();
  const col = range.getColumn();
  if (row < DATA_START_ROW || row > DATA_END_ROW) return;
  if (!DATA_COLS.includes(col)) return;
  const value = range.getValue();
  const color = VALUE_COLOR_MAP[value];
  if (color) {
    range.setBackground(color);
    range.setFontColor(TEXT_COLOR_MAP[value] || '#000000');
  }
}

// ═══════════════════════════════════════════════════════════════════
// EXISTING — Personal Itinerary System
// ═══════════════════════════════════════════════════════════════════

const ITIN_SHEET_ID = '1GlT_Qu4Fi3gl0qSMp798mg0wKEEG1_-iSNrVjQkV8wI';
const ITIN_GROUPS_TAB = 'groups';
const ITIN_SCHEDULE_TAB = 'משמרות הערכה ועיבוד';
const ITIN_SHIFT_1 = 'בוקר';
const ITIN_SHIFT_2 = 'לילה';

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('personal itinerary')
    .addItem('לוח משמרות אישי', 'showSidebar')
    .addItem('החלפת משמרת', 'showSwapSidebar')
    .addToUi();
}

function showSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('Sidebar')
    .setTitle('לוח משמרות אישי')
    .setWidth(340);
  SpreadsheetApp.getUi().showSidebar(html);
}

function norm(s) {
  if (!s) return '';
  return String(s).trim()
    .replace(/\u2019/g, "'").replace(/\u2018/g, "'").replace(/\u05f3/g, "'")
    .replace(/\s+/g, ' ');
}

function pad2(n) { return String(n).padStart(2, '0'); }

function getDayNameHebrew(d) {
  return ['ראשון','שני','שלישי','רביעי','חמישי','שישי','שבת'][d.getDay()];
}

function ddmmyyToISO(dd, mm, yy) {
  return (2000+parseInt(yy)) + '-' + pad2(parseInt(mm)) + '-' + pad2(parseInt(dd));
}

function getPeople() {
  const ss = SpreadsheetApp.openById(ITIN_SHEET_ID);
  const sheet = ss.getSheetByName(ITIN_GROUPS_TAB);
  const data = sheet.getRange(2, 1, 14, 6).getValues();
  const people = [];
  data.forEach(function(row) {
    const n1 = norm(row[0]);
    if (n1) people.push({name: n1, email: String(row[1]).trim(), team: 'הערכה'});
    const n2 = norm(row[3]);
    if (n2) people.push({name: n2, email: String(row[4]).trim(), team: 'עיבוד'});
  });
  return people;
}

function getShifts(personName, startDate, endDate) {
  const ss = SpreadsheetApp.openById(ITIN_SHEET_ID);
  const sheet = ss.getSheetByName(ITIN_SCHEDULE_TAB);
  const nName = norm(personName);
  const numCols = 60;
  const headerR = sheet.getRange(3, 2, 1, numCols).getValues()[0];
  const t1s1 = sheet.getRange(4, 2, 1, numCols).getValues()[0];
  const t1s2 = sheet.getRange(5, 2, 1, numCols).getValues()[0];
  const t2s1 = sheet.getRange(8, 2, 1, numCols).getValues()[0];
  const t2s2 = sheet.getRange(9, 2, 1, numCols).getValues()[0];
  const results = [];
  // Convert to numeric YYYYMMDD for timezone-proof comparison
  function dateToNum(s) {
    const p = s.split('-');
    return parseInt(p[0])*10000 + parseInt(p[1])*100 + parseInt(p[2]);
  }
  const startNum = dateToNum(startDate);
  const endNum   = dateToNum(endDate);
  for (let i = 0; i < numCols; i++) {
    const m = String(headerR[i]).match(/(\d{2})\/(\d{2})\/(\d{2})/);
    if (!m) continue;
    const iso = ddmmyyToISO(m[1], m[2], m[3]);
    const shiftDate = new Date(iso + 'T12:00:00');
    const dayName = getDayNameHebrew(shiftDate);
    const dateNum = dateToNum(iso);
    if (dateNum < startNum || dateNum > endNum) continue;
    // Morning: check team 1 row 4 + team 2 row 8
    if ([norm(t1s1[i]), norm(t2s1[i])].some(function(n) { return n === nName; }))
      results.push({date: iso, dayName: dayName, shiftType: ITIN_SHIFT_1});
    // Night: check team 1 row 5 + team 2 row 9
    if ([norm(t1s2[i]), norm(t2s2[i])].some(function(n) { return n === nName; }))
      results.push({date: iso, dayName: dayName, shiftType: ITIN_SHIFT_2});
  }
  results.sort(function(a,b){return a.date<b.date?-1:a.date>b.date?1:0;});
  return results;
}

// ─── DEBUG ────────────────────────────────────────────────────────────────────
function debugNadav() {
  const ss = SpreadsheetApp.openById(ITIN_SHEET_ID);
  const sheet = ss.getSheetByName(ITIN_SCHEDULE_TAB);
  const numCols = 60;
  const headerR = sheet.getRange(3, 2, 1, numCols).getValues()[0];
  const t1s1 = sheet.getRange(4, 2, 1, numCols).getValues()[0];
  const t1s2 = sheet.getRange(5, 2, 1, numCols).getValues()[0];
  const t2s1 = sheet.getRange(8, 2, 1, numCols).getValues()[0];
  const t2s2 = sheet.getRange(9, 2, 1, numCols).getValues()[0];
  
  const nName = norm("נדב רבינוביץ'");
  
  // Check ALL columns that have dates
  for (let i = 0; i < 30; i++) {
    const header = String(headerR[i]);
    const m = header.match(/(\d{2})\/(\d{2})\/(\d{2})/);
    if (!m) continue;
    
    const iso = ddmmyyToISO(m[1], m[2], m[3]);
    const dateNum = dateToNum(iso);
    const t1s1n = norm(t1s1[i] || '');
    const t1s2n = norm(t1s2[i] || '');
    const t2s1n = norm(t2s1[i] || '');
    const t2s2n = norm(t2s2[i] || '');
    
    const t1s1match = t1s1n === nName;
    const t1s2match = t1s2n === nName;
    
    if (t1s1match || t1s2match) {
      Logger.log('COL %s | date=%s | dateNum=%s | t1s1=[%s] match=%s | t1s2=[%s] match=%s',
        i, iso, dateNum, t1s1[i] || '(empty)', t1s1match, t1s2[i] || '(empty)', t1s2match);
      Logger.log('  t1s1 CHARS: %s', (t1s1[i]||'').split('').map(function(c){return c.charCodeAt(0);}).join(','));
      Logger.log('  nName CHARS: %s', nName.split('').map(function(c){return c.charCodeAt(0);}).join(','));
    }
  }
  
  // Now run getShifts and log results
  const shifts = getShifts("נדב רבינוביץ'", "2026-05-10", "2026-05-23");
  Logger.log('getShifts returned %s shifts:', shifts.length);
  shifts.forEach(function(s) {
    Logger.log('  %s %s %s', s.date, s.dayName, s.shiftType);
  });
}

function emailItinerary(personName, startDateStr, endDateStr) {
  try {
    const shifts = getShifts(personName, startDateStr, endDateStr);
    const people = getPeople();
    const person = people.find(function(p){return norm(p.name)===norm(personName);});
    if (!person || !person.email)
      return {success: false, error: 'לא נמצאה כתובת אימייל עבור ' + personName};
    if (shifts.length === 0)
      return {success: false, error: 'לא נמצאו משמרות בטווח התאריכים הנבחר'};
    const tz = Session.getScriptTimeZone();
    const ics = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Miluim//EN','CALSCALE:GREGORIAN','METHOD:PUBLISH'];
    shifts.forEach(function(s) {
      const p = s.date.split('-');
      const yr = p[0], mo = p[1], dy = p[2];
      let ds, de, st, dt;
      if (s.shiftType === ITIN_SHIFT_1) {
        ds = yr+mo+dy+'T060000'; de = yr+mo+dy+'T180000';
        st = 'משמרת בוקר'; dt = '06:00-18:00';
      } else {
        ds = yr+mo+dy+'T180000';
        const d = new Date(s.date+'T12:00:00'); d.setDate(d.getDate()+1);
        de = d.getFullYear()+pad2(d.getMonth()+1)+pad2(d.getDate())+'T060000';
        st = 'משמרת לילה'; dt = '18:00-06:00';
      }
      ics.push('BEGIN:VEVENT');
      ics.push('UID:miluim-'+personName.replace(/\s/g,'')+'-'+s.date+'-'+s.shiftType+'@miluim');
      ics.push('DTSTART;TZID='+tz+':'+ds);
      ics.push('DTEND;TZID='+tz+':'+de);
      ics.push('SUMMARY:'+st);
      ics.push('DESCRIPTION:'+st+'\\n'+dt);
      ics.push('END:VEVENT');
    });
    ics.push('END:VCALENDAR');
    const blob = Utilities.newBlob(ics.join('\r\n'), 'application/octet-stream', 'miluim-schedule.ics');
    GmailApp.sendEmail(person.email, 'לוח משמרות אישי - '+personName,
      'שלום '+personName+',\n\nמצורף לוח המשמרות שלך לתאריכים '+startDateStr+' - '+endDateStr+
      '.\n\nסה"כ '+shifts.length+' משמרות.\n\nבהצלחה!',
      {attachments: [blob], name: 'מערכת משמרות מילואים'});
    return {success: true, count: shifts.length};
  } catch(e) { return {success: false, error: e.message}; }
}

// ═══════════════════════════════════════════════════════════════════
// NEW — Swap Shift Sidebar
// ═══════════════════════════════════════════════════════════════════

function showSwapSidebar() {
  const html = HtmlService.createHtmlOutputFromFile('SwapSidebar')
    .setTitle('החלפת משמרת')
    .setWidth(380);
  SpreadsheetApp.getUi().showSidebar(html);
}

// Get future shifts with team info for a person (used by swap sidebar)
function getMyShiftsWithTeam(personName) {
  const ss = SpreadsheetApp.openById(ITIN_SHEET_ID);
  const sheet = ss.getSheetByName(ITIN_SCHEDULE_TAB);
  const normName = norm(personName);
  const numCols = 60;

  const headers = sheet.getRange(3, 2, 1, numCols).getValues()[0];
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

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  for (let i = 0; i < numCols; i++) {
    const header = String(headers[i] || '');
    const match = header.match(dateRegex);
    if (!match) continue;

    const dateStr = match[1] + '/' + match[2] + '/20' + match[3];
    const isoDate = ddmmyyToISO(match[1], match[2], match[3]);
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

// Get all people's names for the swap dropdown
function getPeopleNames() {
  const people = getPeople();
  return people.map(p => p.name);
}

// Submit a swap request to the Swaps staging tab
function submitSwapRequest(personName, shiftDate, shiftType, team) {
  try {
    const ss = SpreadsheetApp.openById(ITIN_SHEET_ID);
    let swapSheet = ss.getSheetByName('Swaps');
    if (!swapSheet) {
      swapSheet = ss.insertSheet('Swaps');
      swapSheet.getRange(1, 1, 1, 6).setValues([[
        'תאריך בקשה', 'שם', 'תאריך משמרת', 'סוג', 'צוות', 'סטטוס'
      ]]);
      swapSheet.setFrozenRows(1);
    }

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

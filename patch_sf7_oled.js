const fs = require('fs');

const nodes = [
  'development/recent/nodes/Node_A/Node_A.ino',
  'development/recent/nodes/Node_B/Node_B.ino',
  'development/recent/nodes/Node_C/Node_C.ino'
];

for (let file of nodes) {
  if (!fs.existsSync(file)) continue;
  let code = fs.readFileSync(file, 'utf8');

  // 1. Revert LORA_SF to 7
  code = code.replace(/#define LORA_SF\s+9/, '#define LORA_SF        7');

  // 2. Add Message Page to OLED
  if (!code.includes('drawPage5')) {
    code = code.replace('#define UI_PAGES           5', '#define UI_PAGES           6');
    
    const page5 = `// ---- page 5: MESSAGE -----------------------------------------------------
void drawPage5() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- MESSAGE --      5/5");
  if (lastMsgTime == 0) {
    snprintf(l[1], sizeof(l[1]), "No messages yet");
    l[2][0] = l[3][0] = l[4][0] = '\\0';
  } else {
    char ageStr[8];
    fmtAge(millis() - lastMsgTime, ageStr, sizeof(ageStr));
    snprintf(l[1], sizeof(l[1]), "From: %-4s   %s ago", lastMsgFrom, ageStr);
    
    // Split lastMsgText (up to 40 chars) across lines 2 and 3
    char m1[22] = {0}, m2[22] = {0};
    strncpy(m1, lastMsgText, 21);
    if (strlen(lastMsgText) > 21) strncpy(m2, lastMsgText + 21, 21);
    snprintf(l[2], sizeof(l[2]), "%s", m1);
    snprintf(l[3], sizeof(l[3]), "%s", m2);
    l[4][0] = '\\0';
  }
  oledPush(l);
}

void drawUI() {`;
    code = code.replace('void drawUI() {', page5);

    // Update drawUI switch statement
    code = code.replace('else if (uiPage == 4) drawPage4();\n  else                  drawPage0();',
                        'else if (uiPage == 4) drawPage4();\n  else if (uiPage == 5) drawPage5();\n  else                  drawPage0();');

    // Update page numbers on other pages
    code = code.replace(/"NODE %s  SF%d  w%d  1\/5"/g, '"NODE %s  SF%d  w%d  1/6"');
    code = code.replace(/"NODE %s  SF%d      1\/5"/g, '"NODE %s  SF%d      1/6"');
    code = code.replace(/"-- LINKS --   %u up 2\/5"/g, '"-- LINKS --   %u up 2/6"');
    code = code.replace(/"-- ROUTES -- %u ok 3\/5"/g, '"-- ROUTES -- %u ok 3/6"');
    code = code.replace(/"-- POSITIONS --    4\/5"/g, '"-- POSITIONS --    4/6"');
    code = code.replace(/"-- GPS & TEAM --   5\/5"/g, '"-- GPS & TEAM --   5/6"');
    code = code.replace(/"-- MESSAGE --      5\/5"/g, '"-- MESSAGE --      6/6"'); // Fix what we just inserted
  }

  // 3. Auto-switch to page 5 on message
  const msgRxStr = `if (isBcast) buzzerBeep(1200, 200); // notify for broadcast
      Serial.printf("\\n>>> MESSAGE from %s after %u hop(s): %s\\n\\n",
                    p.src, hops, p.payload);`;
  const newMsgRxStr = `if (isBcast) buzzerBeep(1200, 200); // notify for broadcast
      Serial.printf("\\n>>> MESSAGE from %s after %u hop(s): %s\\n\\n",
                    p.src, hops, p.payload);
      uiPage = 5;
      pageTimer.begin(10000, UI_PAGE_MS); // Hold on msg page for 10s
      drawUI();`;
  if (!code.includes('uiPage = 5;')) {
    code = code.replace(msgRxStr, newMsgRxStr);
  }

  fs.writeFileSync(file, code);
}

// Update Rover
let roverFile = 'development/recent/rover/Node_Rover.ino';
if (fs.existsSync(roverFile)) {
  let code = fs.readFileSync(roverFile, 'utf8');
  code = code.replace(/#define LORA_SF\s+9/, '#define LORA_SF        7');
  
  if (!code.includes('drawPage6')) {
    code = code.replace('#define UI_PAGES           6', '#define UI_PAGES           7');
    
    const page6 = `// ---- page 6: MESSAGE -----------------------------------------------------
void drawPage6() {
  char l[5][26];
  snprintf(l[0], sizeof(l[0]), "-- MESSAGE --      7/7");
  if (lastMsgTime == 0) {
    snprintf(l[1], sizeof(l[1]), "No messages yet");
    l[2][0] = l[3][0] = l[4][0] = '\\0';
  } else {
    char ageStr[8];
    fmtAge(millis() - lastMsgTime, ageStr, sizeof(ageStr));
    snprintf(l[1], sizeof(l[1]), "From: %-4s   %s ago", lastMsgFrom, ageStr);
    
    char m1[22] = {0}, m2[22] = {0};
    strncpy(m1, lastMsgText, 21);
    if (strlen(lastMsgText) > 21) strncpy(m2, lastMsgText + 21, 21);
    snprintf(l[2], sizeof(l[2]), "%s", m1);
    snprintf(l[3], sizeof(l[3]), "%s", m2);
    l[4][0] = '\\0';
  }
  oledPush(l);
}

void drawUI() {`;
    code = code.replace('void drawUI() {', page6);

    code = code.replace('else if (uiPage == 5) drawPage5();\n  else                  drawPage0();',
                        'else if (uiPage == 5) drawPage5();\n  else if (uiPage == 6) drawPage6();\n  else                  drawPage0();');

    code = code.replace(/"NODE %s  SF%d      1\/6"/g, '"NODE %s  SF%d      1/7"');
    code = code.replace(/"-- LINKS --   %u up 2\/6"/g, '"-- LINKS --   %u up 2/7"');
    code = code.replace(/"-- ROUTES -- %u ok 3\/6"/g, '"-- ROUTES -- %u ok 3/7"');
    code = code.replace(/"-- POSITIONS --    4\/6"/g, '"-- POSITIONS --    4/7"');
    code = code.replace(/"-- GPS & TEAM --   5\/6"/g, '"-- GPS & TEAM --   5/7"');
    code = code.replace(/"-- ROVER --        6\/6"/g, '"-- ROVER --        6/7"');
  }

  const msgRxStrRov = `snprintf(lastMsgFrom, sizeof(lastMsgFrom), "%s", p.src);
      snprintf(lastMsgText, sizeof(lastMsgText), "%s", p.payload);
      lastMsgTime = millis();
      Serial.printf("\\n>>> MESSAGE from %s after %u hop(s): %s\\n\\n",
                    p.src, hops, p.payload);`;
  const newMsgRxStrRov = `snprintf(lastMsgFrom, sizeof(lastMsgFrom), "%s", p.src);
      snprintf(lastMsgText, sizeof(lastMsgText), "%s", p.payload);
      lastMsgTime = millis();
      Serial.printf("\\n>>> MESSAGE from %s after %u hop(s): %s\\n\\n",
                    p.src, hops, p.payload);
      uiPage = 6;
      pageTimer.begin(10000, UI_PAGE_MS);
      drawUI();`;
  if (!code.includes('uiPage = 6;')) {
    code = code.replace(msgRxStrRov, newMsgRxStrRov);
  }

  fs.writeFileSync(roverFile, code);
}

// Update pi/sx1278.py
let piFile = 'development/pi/sx1278.py';
if (fs.existsSync(piFile)) {
  let code = fs.readFileSync(piFile, 'utf8');
  code = code.replace('SF = 9', 'SF = 7');
  fs.writeFileSync(piFile, code);
}

console.log("Patched everything!");

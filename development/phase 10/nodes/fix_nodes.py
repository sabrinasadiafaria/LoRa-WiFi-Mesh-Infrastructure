import os

src_dir = r"c:\Users\Lenovo\Documents\GitHub\LoRa-WiFi-Mesh-Infrastructure\development\phase 9"
dst_dir = r"c:\Users\Lenovo\Documents\GitHub\LoRa-WiFi-Mesh-Infrastructure\development\phase 10\nodes"

for name, nid in [("Node A", "A"), ("Node B", "B"), ("Node C", "C")]:
    src = os.path.join(src_dir, f"{name}.md")
    dst = os.path.join(dst_dir, f"Node_{nid}.ino")
    
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Extract just the code from the markdown file if it has markdown formatting
    # Note: The phase 9 .md files are actually pure C++ code despite the .md extension.
    
    # 1. Add Buzzer and Stat Button definitions
    content = content.replace("#define PIN_SOS_BUTTON  4", 
                              "#define PIN_SOS_BUTTON  4\n#define PIN_BUZZER     25\n#define PIN_BTN_STAT   13")
    
    # 2. Add pinModes in setup()
    # Find the line pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);
    content = content.replace("pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);",
                              "pinMode(PIN_SOS_BUTTON, INPUT_PULLUP);\n  pinMode(PIN_BUZZER, OUTPUT);\n  pinMode(PIN_BTN_STAT, INPUT_PULLUP);")
    
    # 3. Modify sosTrigger to sound the buzzer
    content = content.replace("void sosTrigger(const char *reason) {",
                              "void sosTrigger(const char *reason) {\n  for(int i=0; i<3; i++) { tone(PIN_BUZZER, 2500, 100); delay(150); }")
    
    # 4. Add Stat button handling in handleButtons()
    # Find handleButtons() function and inject the stat button logic
    stat_btn_logic = """
  static bool statPrev = HIGH;
  static unsigned long statPressMs = 0;
  bool statCurr = digitalRead(PIN_BTN_STAT);
  if (statCurr == LOW && statPrev == HIGH) {
    statPressMs = now;
    tone(PIN_BUZZER, 2200, 30);
  } else if (statCurr == HIGH && statPrev == LOW) {
    if (now - statPressMs >= 2000) {
      sendReport("VICTIM_FOUND");
      tone(PIN_BUZZER, 2500, 200);
    } else {
      if (strcmp(myStatus, "AVAILABLE") == 0) strncpy(myStatus, "SEARCHING", sizeof(myStatus));
      else if (strcmp(myStatus, "SEARCHING") == 0) strncpy(myStatus, "NEED_ASSIST", sizeof(myStatus));
      else strncpy(myStatus, "AVAILABLE", sizeof(myStatus));
      sendStatus(myStatus);
      oledInvalidate();
    }
  }
  statPrev = statCurr;
"""
    content = content.replace("  sosPrev = sosCurr;\n}", "  sosPrev = sosCurr;\n" + stat_btn_logic + "\n}")
    
    with open(dst, "w", encoding="utf-8") as f:
        f.write(content)
        
print("Successfully restored Phase 9 Captive Portal logic to Phase 10 nodes and added the Buzzer/Status button features!")

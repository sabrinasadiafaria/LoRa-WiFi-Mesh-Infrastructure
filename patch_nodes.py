import os, glob

for node_file in glob.glob('development/recent/nodes/Node_*/Node_*.ino'):
    with open(node_file, 'r', encoding='utf-8') as f:
        code = f.read()

    # Fix UI rendering for messages in portal
    if "$('msgBox').style.display='block';" not in code:
        render_msg = '''  " if(d.sos){ $('wrap').className='wrap sos'; $('sub').textContent='SOS ACTIVE - '+$('sub').textContent }\\n"
  " else { $('wrap').className='wrap'; }\\n"
  " if(d.msgText) { $('msgBox').style.display='block'; $('msgText').textContent=d.msgText; $('msgFrom').textContent='from '+d.msgFrom; }\\n"
'''
        code = code.replace('  " if(d.sos){ $(\'wrap\').className=\'wrap sos\'; $(\'sub\').textContent=\'SOS ACTIVE - \'+$(\'sub\').textContent }\\n"\n  " else { $(\'wrap\').className=\'wrap\'; }\\n"', render_msg)

    # Include lastMsgText in /api/status response
    if '"msgText"' not in code:
        code = code.replace('"\\"sos\\":%d,\\"sosvictim\\":\\"%s\\",\\"sostext\\":\\"%s\\",\\n"\\',
                            '"\\"sos\\":%d,\\"sosvictim\\":\\"%s\\",\\"sostext\\":\\"%s\\",\\n" \\\n           "\\"msgText\\":\\"%s\\",\\"msgFrom\\":\\"%s\\",\\n"')
        code = code.replace('sosAlert ? 1 : 0, sosVictim, sosText,\n           peers, routesJson);',
                            'sosAlert ? 1 : 0, sosVictim, sosText,\n           lastMsgText, lastMsgFrom, peers, routesJson);')

    with open(node_file, 'w', encoding='utf-8') as f:
        f.write(code)

print("Nodes patched phase 2!")

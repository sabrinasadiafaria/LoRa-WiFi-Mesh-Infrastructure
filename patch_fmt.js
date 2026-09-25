const fs = require('fs');
const glob = require('fs').readdirSync('development/recent/nodes', {withFileTypes: true})
  .filter(d => d.isDirectory() && d.name.startsWith('Node_'));

for (let d of glob) {
  let file = `development/recent/nodes/${d.name}/${d.name}.ino`;
  if (!fs.existsSync(file)) continue;
  let code = fs.readFileSync(file, 'utf8');

  // Fix snprintf format string for msgText
  let oldStr = `"\\"sos\\":%d,\\"sosvictim\\":\\"%s\\",\\"sostext\\":\\"%s\\","\n           "\\"peers\\":%s,\\"routes\\":%s}",`;
  let newStr = `"\\"sos\\":%d,\\"sosvictim\\":\\"%s\\",\\"sostext\\":\\"%s\\","\n           "\\"msgText\\":\\"%s\\",\\"msgFrom\\":\\"%s\\","\n           "\\"peers\\":%s,\\"routes\\":%s}",`;
  
  if (code.includes(oldStr)) {
    code = code.replace(oldStr, newStr);
    fs.writeFileSync(file, code);
    console.log(`Patched format string in ${file}`);
  }
}

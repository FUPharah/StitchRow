/* KnitParser — browser port of parse_pattern.py. Self-contained, no network. */
(function(root){
  'use strict';
  var NUM = '\\d+(?:\\.\\d+)?\\.?';
  var CHAIN = new RegExp(NUM + '\\s*\\(\\s*' + NUM + '\\s*\\)' +
    '(?:\\s*' + NUM + '\\s*\\(\\s*' + NUM + '\\s*\\))*(?:\\s*' + NUM + ')?', 'g');
  var ROW_RE = /^\s*(\d+)\.\s*v\s*(?:\(([^)]*)\))?\s*:\s*(.*)$/i;
  var RANGE_ROW_RE = /^\s*(\d+)\.\s*-\s*(\d+)\.\s*v\s*(?:\(([^)]*)\))?\s*:\s*(.*)$/i;
  var CASTON_RE = /Lägg upp\s+([\d\s.,()]+?)\s*m/i;
  var REPEAT_TOTAL_RE = new RegExp('Sticka (?:dessa|ovanstående)\\s+(\\d+)\\s+v(?:.*?totalt)?\\s+(' + NUM + ')\\s+gånger', 'i');
  var REPEAT_EXTRA_RE = new RegExp('Sticka dessa\\s+(\\d+)\\s*v.*?(\\d+)\\.\\s*och\\s*(\\d+)\\.\\s*v\\s+ytterligare\\s+(' + NUM + ')\\s+gånger', 'i');
  var UNTIL_RE = new RegExp('tills det är\\s+(' + NUM + ')\\s*m', 'i');
  var SOM_RE = /^Som\s+(\d+)\.\s*v/i;
  var COUNT_RE = /=\s*(\d+)\s*m/i;
  var SECTION_STOP = ['BESKRIVNING', 'Montering', 'Om ', 'Fäst ', 'Nu sys ',
    'Luvan är nu färdigstickad', 'Det är nu en i-cordkant', 'Nu är höger sida',
    'Mette Wendelboe', 'Trevlig stickning'];

  function cleanNum(s){ return parseInt(String(s).replace(/[^\d]/g, ''), 10) || 0; }
  function pickSize(text, idx){
    return text.replace(CHAIN, function(m){
      var nums = m.match(/\d+(?:\.\d+)?/g) || [];
      if (nums.length < 2) return m;
      return nums[Math.min(idx, nums.length - 1)];
    });
  }
  function stitchDelta(instr){
    var s = instr.toLowerCase(), d = 0, m;
    d += (s.match(/ök/g) || []).length;
    d += (s.match(/minsk-[hv]/g) || []).length * -1;
    if (s.indexOf('sätt de första 3 m till vila') >= 0) d -= 3;
    if (s.indexOf('vilande m i i-corden tillbaka') >= 0) d += 3;
    if (s.indexOf('maska av de första 3 m') >= 0 && s.indexOf('sista 3 m') >= 0) d -= 6;
    return d;
  }
  function tagsFor(instr){
    var s = instr.toLowerCase(), t = [];
    if (/ök/.test(s)) t.push('increase');
    if (/minsk-[hv]/.test(s)) t.push('decrease');
    if (/i-cord|lyft|maska av|till vila/.test(s)) t.push('special');
    if (/resår/.test(s)) t.push('rib');
    if (/\bam\b|amask/.test(s)) t.push('purl');
    else if (/\brm\b|rätstickning|sticka rm/.test(s)) t.push('knit');
    return t.length ? t : ['knit'];
  }
  function translate(instr){
    var s = instr.trim();
    if (/maska av de första 3 m/i.test(s))
      return 'Bind off the first 3 sts knitwise and the last 3 sts purlwise.';
    if (/vilande m i i-corden tillbaka/i.test(s))
      return 'Knit to end; with yarn in front, return the held i-cord sts to the needle with the wrong side facing you so they continue the other sts.';
    s = s.replace(/Sätt de första 3 m till vila på en stickmarkör eller en bit restgarn/ig, 'place the first 3 sts on hold on a marker or scrap yarn');
    s = s.replace(/Sticka rm tills det är (\d+) m kvar på st/ig, function(m, n){ return 'knit to last ' + n + ' sts'; });
    s = s.replace(/sticka rm tills det är (\d+) m kvar på st/ig, function(m, n){ return 'knit to last ' + n + ' sts'; });
    s = s.replace(/lyft de 3 sista m a löst av med garnet framför arbetet/ig, 'slip the last 3 sts purlwise with yarn in front');
    s = s.replace(/Sticka (\d+) rm/g, function(m, n){ return 'k' + n; });
    s = s.replace(/\b1 rm\b/g, 'k1');
    s = s.replace(/\bminsk-h\b/ig, 'k2tog');
    s = s.replace(/\bminsk-v\b/ig, 'ssk');
    s = s.replace(/ök/ig, 'inc');
    s = s.replace(/Sticka resår \([^)]*\)/ig, 'Work rib (k1, p1)');
    s = s.replace(/upprepa från \* till \* v ut/ig, 'repeat from * to * to end');
    s = s.replace(/lyft 1 m a löst av med garnet framför arbetet/ig, 'slip 1 st purlwise with yarn in front');
    s = s.replace(/Sticka \*/g, 'Knit *');
    s = s.replace(/Sticka rm v ut/ig, 'knit to end');
    s = s.replace(/Sticka rm\b/g, 'knit all sts');
    s = s.replace(/\bam\b/g, 'purl');
    s = s.replace(/Sticka resår \([^)]*\)/ig, 'Work rib (k1, p1)');
    s = s.replace(/lyft 1 m a löst av med garnet bakom arbetet/ig, 'slip 1 st purlwise with yarn behind');
    s = s.replace(/\b1 purl\b/g, 'p1');
    s = s.replace(/^[\s,]+|[\s,]+$/g, '');
    if (s) { s = s.charAt(0).toUpperCase() + s.slice(1); if (!/[.!?]$/.test(s)) s += '.'; }
    return s;
  }
  function resolveSom(row, block){
    var m = SOM_RE.exec(row.instr.trim());
    if (m) { var n = parseInt(m[1], 10); if (n >= 1 && n <= block.length) return resolveSom(block[n - 1], block); }
    return row.instr;
  }
  function guessTitle(raw){
    var ls = raw.split('\n');
    for (var i = 0; i < ls.length; i++) {
      var l = ls[i].trim();
      if (l && l.charAt(0) !== '_' && l.length > 3 && !/^\d/.test(l) &&
          /[A-Za-zÅÄÖåäö]/.test(l) && l.length < 60) return l;
    }
    return 'Imported pattern';
  }

  function parse(rawText, sizeIdx){
    var text = pickSize(rawText, sizeIdx);
    var lines = text.split('\n').map(function(l){ return l.trim(); });
    var hasRows = lines.some(function(l){ return ROW_RE.test(l) || RANGE_ROW_RE.test(l); });
    if (!hasRows) return { error: 'No machine-readable rows found. This looks like a chart-based pattern; its rows must be entered manually or read from the chart.',
      title: guessTitle(rawText), preview: rawText.slice(0, 600) };

    var castMatch = CASTON_RE.exec(text);
    var stitches = castMatch ? cleanNum(castMatch[1].match(/\d+/g)[0]) : 0;
    var out = [], pending = [], lastCycle = [];

    function emit(rowdef){
      var instr = rowdef.instr;
      stitches += stitchDelta(instr);
      var cm = COUNT_RE.exec(instr);
      if (cm) stitches = parseInt(cm[1], 10);
      out.push({ instruction: translate(instr), original: instr, tags: tagsFor(instr), stitches: stitches });
    }
    function expandBlock(block, times){
      var resolved = block.map(function(r){ return { n: r.n, side: r.side, instr: resolveSom(r, block) }; });
      for (var k = 0; k < times; k++) resolved.forEach(emit);
      return resolved;
    }
    function flushPending(){
      pending.forEach(function(r){ r.instr = resolveSom(r, pending); emit(r); });
      pending = [];
    }

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i], rm, rrm, m;
      if ((rm = ROW_RE.exec(line))) {
        pending.push({ n: parseInt(rm[1], 10), side: rm[2] || '', instr: (rm[3] || '').trim() }); continue;
      }
      if ((rrm = RANGE_ROW_RE.exec(line))) {
        var a = parseInt(rrm[1], 10), b = parseInt(rrm[2], 10);
        for (var n = a; n <= b; n++) pending.push({ n: n, side: rrm[3] || '', instr: (rrm[4] || '').trim() });
        continue;
      }
      if ((m = REPEAT_EXTRA_RE.exec(line)) && pending.length) {
        var cnt = parseInt(m[1], 10), ra = parseInt(m[2], 10), rb = parseInt(m[3], 10), extra = cleanNum(m[4]);
        var block = pending.slice(pending.length - cnt);
        if (!block.length) block = pending.slice();
        var resolved = expandBlock(block, 1);
        var picked = resolved.filter(function(r){ return r.n === ra || r.n === rb; });
        for (var e = 0; e < extra; e++) picked.forEach(emit);
        lastCycle = resolved; pending = []; continue;
      }
      if ((m = REPEAT_TOTAL_RE.exec(line)) && pending.length) {
        var c2 = parseInt(m[1], 10), times = cleanNum(m[2]);
        var b2 = pending.slice(pending.length - c2);
        if (!b2.length) b2 = pending.slice();
        lastCycle = expandBlock(b2, Math.max(1, times)); pending = []; continue;
      }
      if ((m = UNTIL_RE.exec(line)) && lastCycle.length) {
        var target = cleanNum(m[1]);
        var net = lastCycle.reduce(function(s, r){ return s + stitchDelta(r.instr); }, 0), guard = 0;
        if (net > 0) {
          while (stitches < target && guard < 2000) { for (var p = 0; p < lastCycle.length && stitches < target; p++) emit(lastCycle[p]); guard++; }
        } else if (net < 0) {
          while (stitches > target && guard < 2000) { for (var q = 0; q < lastCycle.length && stitches > target; q++) emit(lastCycle[q]); guard++; }
        }
        continue;
      }
      if (pending.length && (line === '' || SECTION_STOP.some(function(s){ return line.indexOf(s) === 0; }))) {
        if (line === '') {
          var j = i + 1; while (j < lines.length && lines[j] === '') j++;
          var nxt = lines[j] || '';
          if (ROW_RE.test(nxt) || RANGE_ROW_RE.test(nxt) || REPEAT_TOTAL_RE.test(nxt) ||
              REPEAT_EXTRA_RE.test(nxt) || UNTIL_RE.test(nxt) ||
              /^(Sticka |Fortsätt |Nu |De sista)/.test(nxt)) { continue; }
        }
        flushPending(); continue;
      }
      if (pending.length && line && !/^(Sticka dessa|Sticka ovanstående|Sticka fram|Sticka nu|Fortsätt|Lägg|Nu stickas|Det |Därefter|Vari |Sjal |På nästa)/.test(line)) {
        if (!/^\d+$/.test(line) && line.indexOf('www.') !== 0 && line.indexOf('©') < 0)
          pending[pending.length - 1].instr += ' ' + line;
      }
    }
    flushPending();
    if (!out.length) return { error: 'Could not extract rows from this pattern.', title: guessTitle(rawText), preview: rawText.slice(0, 600) };

    var groups = [], count = 0;
    for (var k = 0; k < out.length; k += 8) {
      var chunk = out.slice(k, k + 8), steps = chunk.map(function(s){ count++; return { label: String(count), instruction: s.instruction, original: s.original, tags: s.tags, stitches: s.stitches }; });
      groups.push({ name: 'Rows ' + (k + 1) + '–' + (k + chunk.length), steps: steps });
    }
    var sizeCount = 1;
    if (castMatch) { var ns = castMatch[1].match(/\d+/g) || []; sizeCount = Math.max(1, ns.length); }
    return { title: guessTitle(rawText), note: out.length + ' rows · size option ' + (sizeIdx + 1) + ' · cast on ' + (castMatch ? cleanNum(castMatch[1].match(/\d+/g)[0]) : 0) + ' sts',
      groups: groups, row_count: out.length, size_count: sizeCount };
  }

  function sizeCount(raw){
    var m = CASTON_RE.exec(raw);
    if (!m) return 1;
    var chain = new RegExp(CHAIN.source, 'g').exec(m[1]);
    var nums = (chain ? chain[0] : m[1]).match(/\d+/g) || [];
    return Math.max(1, nums.length);
  }

  function pickSizeEnglish(text, idx){
    var re=/(\d+)\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)/g;
    return text.replace(re,function(m){var v=[];for(var i=1;i<arguments.length-2;i++)v.push(arguments[i]);return v[Math.min(idx,v.length-1)]||m;});
  }
  function englishDelta(instr){
    var s=instr.toLowerCase(),d=0,m;
    var word={two:2,three:3,four:4,five:5,six:6,seven:7,eight:8};
    var mult=1,w=s.match(/\b(two|three|four|five|six|seven|eight)\b/);if(w)mult=word[w[1]];
    d+=(s.match(/\bm1[rl]p?\b/g)||[]).length*mult;
    d-=(s.match(/\bk2tog\b/g)||[]).length*mult;
    d-=(s.match(/\bssk\b/g)||[]).length*mult;
    if((m=/put the next (\d+) stitches up to the next marker onto scrap yarn/.exec(s))) d-=parseInt(m[1],10);
    if((m=/cast on (\d+) underarm stitches/.exec(s))) d+=parseInt(m[1],10);
    if((m=/pick up (\d+) stitches from the underarm cast on/.exec(s))) d+=parseInt(m[1],10);
    if((m=/cast on (\d+) stitches/.exec(s))) { d+=parseInt(m[1],10); }
    if((m=/you should have (\d+) stitches/.exec(s))) return null;
    return d;
  }
  function englishTags(instr){
    var s=instr.toLowerCase(),t=[];
    if(/\bm1[rl]p?\b/.test(s))t.push('increase');
    if(/\bk2tog\b|\bssk\b/.test(s))t.push('decrease');
    if(/\bp\b|purl/.test(s)&&/\bk\b|knit/.test(s))t.push('rib');
    else if(/\bp\b|purl/.test(s))t.push('purl');
    else t.push('knit');
    if(/marker|turn|scrap yarn|bind off|short row/.test(s))t.push('special');
    return t;
  }
  function parseEnglish(rawText, sizeIdx){
    var text=pickSizeEnglish(rawText,sizeIdx);
    var lines=text.split('\n').map(function(l){return l.trim();});
    var cast=0;
    for(var i=0;i<lines.length;i++){var m=/cast on (\d+) stitches/i.exec(lines[i]);if(m){cast=parseInt(m[1],10);break;}}
    var stitches=cast,out=[],pending=[];
    function emit(instr){
      var md=englishDelta(instr);
      if(md===null){var mm=/you should have (\d+) stitches/i.exec(instr);if(mm)stitches=parseInt(mm[1],10);}
      else stitches+=md;
      out.push({instruction:instr.replace(/\s+/g,' ').trim(),tags:englishTags(instr),stitches:stitches});
    }
    for(var j=0;j<lines.length;j++){
      var line=lines[j],m;
      if((m=/^(Round|Row)\s+(\d+)\s*:?\s*(.*)$/i.exec(line))){
        pending.push({n:parseInt(m[2],10),instr:(m[3]||'').trim()});continue;
      }
      if((m=/^Decrease round\s*:?\s*(.*)$/i.exec(line))){pending.push({n:'D',instr:'Decrease round: '+(m[1]||'')});continue;}
      if((m=/^Work (rounds|rows) (\d+)(?: and (\d+))? a total of (\d+) times/i.exec(line))){
        var nums=[parseInt(m[2],10)];if(m[3])nums.push(parseInt(m[3],10));
        var block=pending.filter(function(r){return nums.indexOf(r.n)>=0;});
        if(block.length){var times=parseInt(m[4],10);for(var k=1;k<times;k++)block.forEach(function(r){emit(r.instr);});}
        continue;
      }
      if((m=/^Work (rounds|rows) (\d+)\s*-\s*(\d+) a total of (\d+) times/i.exec(line))){
        var a=parseInt(m[2],10),b=parseInt(m[3],10);
        var blk=pending.filter(function(r){return r.n>=a&&r.n<=b;});
        if(blk.length){var tm=parseInt(m[4],10);for(var q=1;q<tm;q++)blk.forEach(function(r){emit(r.instr);});}
        continue;
      }
      if(/^you should have \d+ stitches/i.test(line)){emit(line);continue;}
      if(pending.length&&line&&!/^(Round|Row|Option|Yoke|Body|Arms|Pattern|Cast|Join|Switch|Choose|If|Begin|Knit|Continue|Note|To finish|Now|Remove|Transfer|K in|Work in|Select|The |For |These |Alternatively|Measure|On )/.test(line)){
        if(!/^www\.|^https?:|^I’d|^Thanks|^Instagram/.test(line))pending[pending.length-1].instr+=' '+line;
      }
    }
    pending.forEach(function(r){emit(r.instr);});
    if(!out.length)return null;
    var groups=[],cnt=0;
    for(var k=0;k<out.length;k+=8){var ch=out.slice(k,k+8);groups.push({name:'Rows '+(k+1)+'–'+(k+ch.length),steps:ch.map(function(x){cnt++;return{label:String(cnt),instruction:x.instruction,tags:x.tags,stitches:x.stitches};})});}
    return {title:'Step By Step Sweater',note:out.length+' rows · size '+(sizeIdx+1)+' of 7 · cast on '+cast+' sts',groups:groups,row_count:out.length,size_count:7,english:true};
  }

  root.KnitParser = { parse: parse, parseEnglish: parseEnglish, sizeCount: sizeCount, pickSize: pickSize };
  var pdfExtract = function(){ return ''; };
})(window);

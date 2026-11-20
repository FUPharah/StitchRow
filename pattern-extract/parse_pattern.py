#!/usr/bin/env python3
"""PDF knitting pattern -> row JSON for the tracker.

Handles Swedish PetiteKnit-style patterns (Sophie Hood, Monday Sweater) with
row blocks, repeat counts, size alternatives and stitch-count milestones.
Detects chart-only patterns and returns a clear error instead of guessing.

Usage: parse_pattern.py FILE.pdf --size 0 --out pattern.json
"""
import argparse, json, re, sys
from pypdf import PdfReader

NUM = r'\d+(?:\.\d+)?\.?'
# A size-alternation chain: plain (plain) [plain (plain)]* [plain]?
CHAIN = re.compile(
    NUM + r'\s*\(\s*' + NUM + r'\s*\)'
    r'(?:\s*' + NUM + r'\s*\(\s*' + NUM + r'\s*\))*'
    r'(?:\s*' + NUM + r')?'
)
ROW_RE = re.compile(r'^\s*(\d+)\.\s*v\s*(?:\(([^)]*)\))?\s*:\s*(.*)$')
RANGE_ROW_RE = re.compile(r'^\s*(\d+)\.\s*-\s*(\d+)\.\s*v\s*(?:\(([^)]*)\))?\s*:\s*(.*)$')
CASTON_RE = re.compile(r'Lägg upp\s+([\d\s.,()]+?)\s*m', re.I)
REPEAT_TOTAL_RE = re.compile(r'Sticka (?:dessa|ovanstående)\s+(\d+)\s+v(?:.*?totalt)?\s+(' + NUM + r')\s+gånger', re.I)
REPEAT_EXTRA_RE = re.compile(r'Sticka dessa\s+(\d+)\s*v.*?(\d+)\.\s*och\s*(\d+)\.\s*v\s+ytterligare\s+(' + NUM + r')\s+gånger', re.I)
UNTIL_RE = re.compile(r'tills det är\s+(' + NUM + r')\s*m', re.I)
SOM_RE = re.compile(r'^Som\s+(\d+)\.\s*v', re.I)
COUNT_RE = re.compile(r'=\s*(\d+)\s*m', re.I)
SECTION_STOP = ('BESKRIVNING', 'Montering', 'Om ', 'Fäst ', 'Nu sys ', 'Luvan är nu färdigstickad',
                'Det är nu en i-cordkant', 'Nu är höger sida', 'Mette Wendelboe', 'Trevlig stickning')


def clean_num(s):
    return int(re.sub(r'[^\d]', '', s.split('.')[0]) or 0)


def pick_size(text, idx):
    def repl(m):
        nums = re.findall(r'\d+(?:\.\d+)?', m.group(0))
        if len(nums) < 2:
            return m.group(0)
        i = min(idx, len(nums) - 1)
        return nums[i]
    return CHAIN.sub(repl, text)


def extract_text(pdf):
    reader = PdfReader(pdf)
    parts = []
    for pg in reader.pages:
        t = pg.extract_text() or ''
        parts.append(t.replace('\r', '').replace('\u00ad', ''))
    return '\n'.join(parts)


def stitch_delta(instr):
    s = instr.lower()
    d = 0
    d += len(re.findall(r'\bök\b', s))
    d -= len(re.findall(r'minsk-[hv]', s))
    if 'sätt de första 3 m till vila' in s:
        d -= 3
    if 'vilande m i i-corden tillbaka' in s:
        d += 3
    if 'maska av de första 3 m' in s and 'sista 3 m' in s:
        d -= 6
    return d


def tags_for(instr):
    s = instr.lower()
    tags = []
    if re.search(r'\bök\b', s):
        tags.append('increase')
    if re.search(r'minsk-[hv]', s):
        tags.append('decrease')
    if 'i-cord' in s or 'lyft' in s or 'maska av' in s or 'till vila' in s:
        tags.append('special')
    if 'resår' in s:
        tags.append('rib')
    if re.search(r'\bam\b|amask', s):
        tags.append('purl')
    elif re.search(r'\brm\b|rätstickning|sticka rm', s):
        tags.append('knit')
    return tags or ['knit']


# ---- English translation of the recurring Swedish clauses ----
def translate(instr):
    s = instr.strip()
    # full-sentence special cases
    if re.search(r'maska av de första 3 m', s, re.I):
        return 'Bind off the first 3 sts knitwise and the last 3 sts purlwise.'
    if 'vilande m i i-corden tillbaka' in s.lower():
        return ('Knit to end; with yarn in front, return the held i-cord sts to the needle '
                'with the wrong side facing you so they continue the other sts.')
    # clause-by-clause
    s = re.sub(r'Sätt de första 3 m till vila på en stickmarkör eller en bit restgarn',
               'place the first 3 sts on hold on a marker or scrap yarn', s, flags=re.I)
    s = re.sub(r'[Ss]ticka rm tills det är (\d+) m kvar på st',
               lambda m: 'knit to last ' + m.group(1) + ' sts', s)
    s = re.sub(r'lyft de 3 sista m a löst av med garnet framför arbetet',
               'slip the last 3 sts purlwise with yarn in front', s, flags=re.I)
    s = re.sub(r'[Ss]ticka (\d+) rm', lambda m: 'k' + m.group(1), s)
    s = re.sub(r'\b1 rm\b', 'k1', s)
    s = re.sub(r'\bminsk-h\b', 'k2tog', s, flags=re.I)
    s = re.sub(r'\bminsk-v\b', 'ssk', s, flags=re.I)
    s = re.sub(r'\bök\b', 'inc', s, flags=re.I)
    s = re.sub(r'Sticka resår \(1 rm, 1 am\)', 'Work rib (k1, p1)', s, flags=re.I)
    s = re.sub(r'upprepa från \* till \* v ut', 'repeat from * to * to end', s, flags=re.I)
    s = re.sub(r'lyft 1 m a löst av med garnet framför arbetet',
               'slip 1 st purlwise with yarn in front', s, flags=re.I)
    s = re.sub(r'[Ss]ticka \* ', 'Knit *', s)
    s = re.sub(r'[Ss]ticka rm v ut', 'knit to end', s)
    s = re.sub(r'[Ss]ticka rm\b', 'knit all sts', s)
    s = re.sub(r'\bam\b', 'purl', s)
    s = re.sub(r'Sticka resår \([^)]*\)', 'Work rib (k1, p1)', s, flags=re.I)
    s = re.sub(r'lyft 1 m a löst av med garnet bakom arbetet',
               'slip 1 st purlwise with yarn behind', s, flags=re.I)
    s = re.sub(r'\b1 purl\b', 'p1', s)
    s = s.strip(' ,')
    if s:
        s = s[0].upper() + s[1:]
        if not s.endswith('.'):
            s += '.'
    return s


def resolve_som(row, block):
    m = SOM_RE.match(row['instr'].strip())
    if m:
        n = int(m.group(1))
        if 1 <= n <= len(block):
            return resolve_som(block[n - 1], block)
    return row['instr']


def parse(pdf, size_idx):
    raw = extract_text(pdf)
    text = pick_size(raw, size_idx)
    lines = [l.strip() for l in text.split('\n')]

    # chart-only / no row structure detection
    has_rows = any(ROW_RE.match(l) or RANGE_ROW_RE.match(l) for l in lines)
    if not has_rows:
        return {'error': 'No machine-readable rows found. This looks like a chart-based pattern; '
                         'its rows must be entered manually or read from the chart.',
                'title': guess_title(raw), 'preview': raw[:600]}

    stitches = 0
    m = CASTON_RE.search(text)
    if m:
        stitches = clean_num(m.group(1))

    out = []          # finalized rows
    pending = []      # current block of raw row defs
    last_cycle = []   # last expanded block, for "until N sts" loops

    def emit(rowdef):
        nonlocal stitches
        instr = rowdef['instr']
        stitches += stitch_delta(instr)
        cm = COUNT_RE.search(instr)
        if cm:
            stitches = int(cm.group(1))
        out.append({'instruction': translate(instr), 'original': instr,
                    'tags': tags_for(instr), 'stitches': stitches})

    def expand_block(block, times):
        resolved = [dict(r, instr=resolve_som(r, block)) for r in block]
        for _ in range(times):
            for r in resolved:
                emit(r)
        return resolved

    def flush_pending():
        nonlocal pending
        for r in pending:
            r['instr'] = resolve_som(r, pending)
            emit(r)
        pending = []

    i = 0
    while i < len(lines):
        line = lines[i]
        # join continuation lines into the previous row instruction
        rm = ROW_RE.match(line)
        rrm = RANGE_ROW_RE.match(line)
        if rm:
            pending.append({'n': int(rm.group(1)), 'side': rm.group(2) or '', 'instr': rm.group(3).strip()})
            i += 1
            continue
        if rrm:
            a, b = int(rrm.group(1)), int(rrm.group(2))
            for n in range(a, b + 1):
                pending.append({'n': n, 'side': rrm.group(3) or '', 'instr': rrm.group(4).strip()})
            i += 1
            continue

        # repeat: extra rows variant  "Sticka dessa Nv ... a. och b. v ytterligare X gånger"
        mx = REPEAT_EXTRA_RE.search(line)
        if mx and pending:
            n = int(mx.group(1)); a = int(mx.group(2)); b = int(mx.group(3)); extra = clean_num(mx.group(4))
            block = pending[-n:] if n <= len(pending) else pending[:]
            resolved = expand_block(block, 1)
            picked = [r for r in resolved if r['n'] in (a, b)]
            for _ in range(extra):
                for r in picked:
                    emit(r)
            last_cycle = resolved
            pending = []
            i += 1
            continue

        # repeat: total variant "Sticka dessa Nv X gånger (totalt ...)"
        mt = REPEAT_TOTAL_RE.search(line)
        if mt and pending:
            n = int(mt.group(1)); times = clean_num(mt.group(2))
            block = pending[-n:] if n <= len(pending) else pending[:]
            last_cycle = expand_block(block, max(1, times))
            pending = []
            i += 1
            continue

        # continue-until-stitch-count loop
        mu = UNTIL_RE.search(line)
        if mu and last_cycle:
            target = clean_num(mu.group(1))
            net = sum(stitch_delta(r['instr']) for r in last_cycle)
            guard = 0
            if net > 0:
                while stitches < target and guard < 2000:
                    for r in last_cycle:
                        emit(r)
                        if stitches >= target:
                            break
                    guard += 1
            elif net < 0:
                while stitches > target and guard < 2000:
                    for r in last_cycle:
                        emit(r)
                        if stitches <= target:
                            break
                    guard += 1
            i += 1
            continue

        # section stop -> flush
        if pending and (line.startswith(SECTION_STOP) or line == ''):
            # blank line: only flush if next non-blank is not a continuation/repeat
            if line == '':
                j = i + 1
                while j < len(lines) and lines[j] == '':
                    j += 1
                nxt = lines[j] if j < len(lines) else ''
                if (ROW_RE.match(nxt) or RANGE_ROW_RE.match(nxt) or REPEAT_TOTAL_RE.search(nxt)
                        or REPEAT_EXTRA_RE.search(nxt) or UNTIL_RE.search(nxt)
                        or nxt.startswith(('Sticka ', 'Fortsätt ', 'Nu ', 'De sista'))):
                    i += 1
                    continue
            flush_pending()
            i += 1
            continue

        # continuation of a row instruction
        if pending and line and not line.startswith(('Sticka dessa', 'Sticka ovanstående', 'Sticka fram',
                                                      'Sticka nu', 'Fortsätt', 'Lägg', 'Nu stickas',
                                                      'Det ', 'Därefter', 'Vari', 'Sjal', 'På nästa')):
            if not re.match(r'^\d+$', line) and not line.startswith('www.') and '©' not in line:
                pending[-1]['instr'] += ' ' + line
        i += 1

    flush_pending()

    if not out:
        return {'error': 'Could not extract rows from this pattern.', 'title': guess_title(raw), 'preview': raw[:600]}

    groups = []
    n = 0
    for k in range(0, len(out), 8):
        chunk = out[k:k + 8]
        steps = []
        for j, s in enumerate(chunk):
            n += 1
            steps.append(dict(label=str(n), **s))
        groups.append({'name': 'Rows %d–%d' % (k + 1, k + len(chunk)), 'steps': steps})
    size_count = 1
    if m:
        size_count = max(1, len(re.findall(r'\d+', m.group(1))))
    return {'title': guess_title(raw),
            'note': '%d rows · size option %d · cast on %d sts' % (len(out), size_idx + 1, clean_num(m.group(1)) if m else 0),
            'groups': groups, 'row_count': len(out), 'size_count': size_count}


def guess_title(raw):
    for l in raw.split('\n'):
        l = l.strip()
        if l and not l.startswith('_') and len(l) > 3 and not l[0].isdigit():
            if re.search(r'[A-Za-zÅÄÖåäö]', l) and len(l) < 60:
                return l.title() if l.isupper() else l
    return 'Imported pattern'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--size', type=int, default=0)
    ap.add_argument('--out')
    args = ap.parse_args()
    result = parse(args.pdf, args.size)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    summary = {k: result[k] for k in ('title', 'row_count', 'note', 'error') if k in result}
    if 'groups' in result:
        flat = [s for g in result['groups'] for s in g['steps']]
        summary['first'] = flat[:2]
        summary['last'] = flat[-2:]
        summary['groups'] = len(result['groups'])
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

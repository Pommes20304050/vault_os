with open('templates/dashboard.html', 'rb') as f:
    raw = f.read()

before = len(raw)

# Fix 4: rename LBPH face model → YuNet · SFace in subsystem list
raw = raw.replace(
    b"name: 'LBPH face model',        state: 'LOADED',    note: '0 persons \\u00b7 0 samples'",
    b"name: 'YuNet \\u00b7 SFace',         state: 'LOADED',    note: '0 Personen \\u00b7 0 Bilder'"
)

# Fix 5: update SUBS[5] live from /api/persons in renderPeopleReal
# Insert after the corpusCount update, before the length===0 check
old = (b"if (corEl) corEl.textContent = people.reduce(function(a,p){ return a + (p.count||0); }, 0);\\n\\n"
       b"    if (people.length === 0) {")
new = (b"if (corEl) corEl.textContent = people.reduce(function(a,p){ return a + (p.count||0); }, 0);\\n"
       b"    SUBS[5].note = people.length + ' Personen \\u00b7 ' + people.reduce(function(a,p){ return a + (p.count||0); }, 0) + ' Bilder'; renderSubs();\\n\\n"
       b"    if (people.length === 0) {")
raw = raw.replace(old, new)

after = len(raw)

print('LBPH renamed  :', b'YuNet' in raw)
print('SUBS live     :', b'Personen' in raw and b'renderSubs' in raw)
print(f'File size: {before} -> {after}')

with open('templates/dashboard.html', 'wb') as f:
    f.write(raw)
print('Saved.')

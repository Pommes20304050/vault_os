with open('templates/dashboard.html', 'rb') as f:
    raw = f.read()

before = len(raw)

# Fix 1: confidence not inverted (app.py already sends 0-100% where 100=best)
raw = raw.replace(
    b'Math.max(0, Math.min(100, 100 - rawConf))',
    b'Math.max(0, Math.min(100, rawConf))'
)

# Fix 2+3: hide static HTML overlay boxes (they sit at fixed 33%/20% and don't track the face)
# The OpenCV video stream already draws accurate name+confidence on the frame
raw = raw.replace(
    b'.cam-tag {\\n    position: absolute;',
    b'.cam-tag {\\n    display:none!important; position: absolute;'
)
raw = raw.replace(
    b'.cam-conf {\\n    position: absolute;',
    b'.cam-conf {\\n    display:none!important; position: absolute;'
)

after = len(raw)

print('rawConf fix OK :', b'100 - rawConf' not in raw)
print('cam-tag hidden :', b'cam-tag {\\n    display:none' in raw)
print('cam-conf hidden:', b'cam-conf {\\n    display:none' in raw)
print(f'File size: {before} -> {after}')

with open('templates/dashboard.html', 'wb') as f:
    f.write(raw)
print('Saved.')

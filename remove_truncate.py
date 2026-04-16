import re, glob

for f in glob.glob('c:/Users/hamza/Desktop/LiverX/RFP/rfp_agent/templates/*.html'):
    content = open(f, 'r', encoding='utf-8').read()
    content = re.sub(r'class="text-xl font-bold tracking-tight text-blue-900 truncate" title="Network Safety Company"', r'class="text-xl font-bold tracking-tight text-blue-900"', content)
    content = re.sub(r'class="text-\[10px\] uppercase tracking-widest text-slate-400 font-bold truncate"', r'class="text-[10px] uppercase tracking-widest text-slate-400 font-bold"', content)
    open(f, 'w', encoding='utf-8').write(content)
    print(f"Updated {f}")

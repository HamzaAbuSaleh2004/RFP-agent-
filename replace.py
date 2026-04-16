import re, glob

replacement = r'''\1
  <div class="flex items-center gap-3 mb-10">
    <div class="w-10 h-10 rounded-lg bg-white shadow-sm flex items-center justify-center overflow-hidden shrink-0 border border-slate-100">
      <img alt="Network Safety Logo" class="w-full h-full object-contain p-1" src="/static/logo.png"/>
    </div>
    <div class="flex flex-col overflow-hidden">
      <h1 class="text-xl font-bold tracking-tight text-blue-900 truncate" title="Network Safety Company">Network Safety</h1>
      <p class="text-[10px] uppercase tracking-widest text-slate-400 font-bold truncate">Enterprise Procurement</p>
    </div>
  </div>
  \2'''

for f in glob.glob('c:/Users/hamza/Desktop/LiverX/RFP/rfp_agent/templates/*.html'):
    content = open(f, 'r', encoding='utf-8').read()
    new_content = re.sub(r'(<aside[^>]*>)\s*<div.*?(?:Enterprise Procurement</p>\s*(?:</div>)+)?\s*(<nav class="flex-1 space-y-2">)', replacement, content, flags=re.DOTALL)
    if new_content != content:
        open(f, 'w', encoding='utf-8').write(new_content)
        print(f"Updated {f}")

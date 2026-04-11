import re, os
dir='c:/Users/hamza/Desktop/LiverX/RFP/rfp_agent/templates'
for fname in os.listdir(dir):
    path = os.path.join(dir, fname)
    with open(path, 'r', encoding='utf-8') as f: content = f.read()
    def rep(m):
        b = m.group()
        if 'Dashboard' in b: return b.replace('href="#"', 'href="/"')
        if 'Documents' in b: return b.replace('href="#"', 'href="/documents"')
        if 'Evaluations' in b: return b.replace('href="#"', 'href="/evaluations"')
        if 'AI Assistant' in b: return b.replace('href="#"', 'href="/chat"')
        return b
    content = re.sub(r'<a[^>]*href="#"[^>]*>.*?</a>', rep, content, flags=re.DOTALL)
    with open(path, 'w', encoding='utf-8') as f: f.write(content)

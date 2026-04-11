import re

with open('c:/Users/hamza/Desktop/LiverX/RFP/rfp_agent/templates/rfp_creator.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add marked.js
content = content.replace('</head>', '    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>\n</head>')

# Replace chat history with an empty container
chat_regex = re.compile(r'<div class="flex-grow overflow-y-auto space-y-8 pr-4">.*?(?=<!-- Input Area -->)', re.DOTALL)
content = chat_regex.sub('<div id="chat-messages" class="flex-grow overflow-y-auto space-y-8 pr-4 pb-4"></div>\n', content)

# Add IDs to input and button
content = content.replace('<input class="w-full bg-', '<input id="chat-input" class="w-full bg-')
content = content.replace('<button class="absolute right-3', '<button id="send-button" class="absolute right-3')

# Add JS logic
js_logic = '''
<script>
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    
    // Auto focus
    chatInput.focus();

    function appendUserMessage(text) {
        const div = document.createElement('div');
        div.className = 'flex flex-col items-end gap-3 ml-12';
        div.innerHTML = 
            <div class="bg-primary text-white p-6 rounded-2xl rounded-tr-none shadow-md max-w-[85%]">
                <p class="body-md leading-relaxed"></p>
            </div>
            <span class="text-[10px] uppercase tracking-widest text-slate-400 font-semibold px-2">User • Just now</span>
        ;
        chatMessages.appendChild(div);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    function createAgentMessageContainer() {
        const container = document.createElement('div');
        container.className = 'flex flex-col items-start gap-4 mr-12';
        
        container.innerHTML = 
            <div class="flex items-center gap-3">
                <div class="w-8 h-8 bg-tertiary-fixed-dim rounded-full flex items-center justify-center">
                    <span class="material-symbols-outlined text-primary text-sm" style="font-variation-settings: \\'FILL\\' 1;">auto_awesome</span>
                </div>
                <span class="text-[10px] uppercase tracking-widest text-primary font-bold agent-status">RFP Agent • Thinking...</span>
            </div>
            <div class="bg-surface-container-low p-8 rounded-3xl rounded-tl-none space-y-6 w-full agent-content">
                <div class="markdown-body prose max-w-none text-primary leading-relaxed font-medium"></div>
                <div class="agent-logs hidden bg-white/50 rounded-xl p-4 border-l-4 border-tertiary-fixed-dim flex flex-col gap-2"></div>
            </div>
        ;
        chatMessages.appendChild(container);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return {
            container: container,
            contentDiv: container.querySelector('.markdown-body'),
            statusSpan: container.querySelector('.agent-status'),
            logsDiv: container.querySelector('.agent-logs')
        };
    }

    async function sendMessage() {
        const text = chatInput.value.trim();
        if (!text) return;
        
        appendUserMessage(text);
        chatInput.value = '';
        
        const agentUI = createAgentMessageContainer();
        let markdownBuffer = '';
        let logsBuffer = [];

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, session_id: 'default' })
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder('utf-8');

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.type === 'chunk') {
                                markdownBuffer += data.text;
                                agentUI.contentDiv.innerHTML = marked.parse(markdownBuffer);
                                chatMessages.scrollTop = chatMessages.scrollHeight;
                            } else if (data.type === 'status') {
                                agentUI.statusSpan.innerText = 'RFP Agent • Processing';
                                agentUI.logsDiv.style.display = 'flex';
                                const logEntry = document.createElement('div');
                                logEntry.className = 'flex items-center gap-3 text-xs font-medium text-on-surface-variant';
                                logEntry.innerHTML = <span class="material-symbols-outlined text-sm">history_edu</span><span></span>;
                                agentUI.logsDiv.appendChild(logEntry);
                                chatMessages.scrollTop = chatMessages.scrollHeight;
                            } else if (data.type === 'done') {
                                agentUI.statusSpan.innerText = 'RFP Agent • Completed';
                            } else if (data.type === 'error') {
                                markdownBuffer += "\\n\\n**Error:** " + data.text;
                                agentUI.contentDiv.innerHTML = marked.parse(markdownBuffer);
                            }
                        } catch(e) {}
                    }
                }
            }
        } catch (error) {
            console.error(error);
            agentUI.statusSpan.innerText = 'RFP Agent • Error';
            agentUI.contentDiv.innerHTML = '<span class="text-red-500">Failed to connect to agent.</span>';
        }
    }

    sendButton.addEventListener('click', sendMessage);
    chatInput.addEventListener('keypress', function (e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
</script>
</body>
'''

content = content.replace('</body>', js_logic)

with open('c:/Users/hamza/Desktop/LiverX/RFP/rfp_agent/templates/rfp_creator.html', 'w', encoding='utf-8') as f:
    f.write(content)

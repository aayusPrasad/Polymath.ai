import React, { useState } from 'react';
import { Cpu, Activity, Award, Download, Trash2, Layers, Palette } from 'lucide-react';
import ChatBox from './components/ChatBox';
import AgentTrace from './components/AgentTrace';
import Uploader from './components/Uploader';
import KnowledgeBase from './components/KnowledgeBase';
import QuizModal from './components/QuizModal';
import FlashcardModal from './components/FlashcardModal';
import { fetchPolymathResponse } from './services/api';
import './index.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [latestTrace, setLatestTrace] = useState([]);
  const [latestDomain, setLatestDomain] = useState('');
  const [kbRefresh, setKbRefresh] = useState(0);
  const [isQuizOpen, setIsQuizOpen] = useState(false);
  const [isFlashcardsOpen, setIsFlashcardsOpen] = useState(false);
  const [theme, setTheme] = useState('obsidian'); // obsidian | cyberpunk | midnight

  const handleSendMessage = async (text) => {
    const newMessages = [...messages, { role: 'user', content: text }];
    setMessages(newMessages);
    setIsLoading(true);

    try {
      setLatestTrace([]);
      setLatestDomain('');

      const response = await fetchPolymathResponse(text);
      
      setMessages([...newMessages, { 
        role: 'assistant', 
        content: response.answer,
        citations: response.citations,
        processingTime: response.processing_time_sec
      }]);
      
      setLatestTrace(response.agent_trace || []);
      setLatestDomain(response.domain || '');

    } catch (error) {
      setMessages([...newMessages, { 
        role: 'assistant', 
        content: `**Error:** ${error.message}` 
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportChat = () => {
    if (messages.length === 0) return;
    let markdown = `# Polymath.ai Conversation Export\n\n`;
    messages.forEach((msg) => {
      const role = msg.role === 'user' ? '### 👤 User' : '### 🤖 Polymath Agent';
      markdown += `${role}\n${msg.content}\n\n`;
      if (msg.citations && msg.citations.length > 0) {
        markdown += `**Citations:** ${msg.citations.join(', ')}\n\n`;
      }
    });

    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `polymath_chat_${Date.now()}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const toggleTheme = () => {
    const themes = ['obsidian', 'cyberpunk', 'midnight'];
    const nextTheme = themes[(themes.indexOf(theme) + 1) % themes.length];
    setTheme(nextTheme);
  };

  return (
    <div className={`app-container theme-${theme}`}>
      {/* Left Chat Section */}
      <section className="glass-panel chat-section">
        <header className="header">
          <Cpu size={24} color="var(--accent-blue)" />
          <h2>Polymath.ai</h2>

          <div style={{ flex: 1 }} />

          <button 
            className="action-btn-header highlight-teal" 
            onClick={() => setIsFlashcardsOpen(true)}
            title="Study Flashcards"
          >
            <Layers size={15} />
            <span>Flashcards</span>
          </button>

          <button 
            className="action-btn-header highlight" 
            onClick={() => setIsQuizOpen(true)}
            title="Practice Quiz Generator"
          >
            <Award size={15} />
            <span>Practice Quiz</span>
          </button>

          <button
            className="icon-btn-subtle"
            onClick={toggleTheme}
            title={`Current Theme: ${theme.toUpperCase()} (Click to toggle)`}
            style={{ padding: '0.4rem 0.6rem' }}
          >
            <Palette size={16} />
          </button>

          {messages.length > 0 && (
            <>
              <button 
                className="action-btn-header" 
                onClick={handleExportChat}
                title="Export conversation as Markdown"
              >
                <Download size={15} />
              </button>

              <button 
                className="action-btn-header" 
                onClick={() => setMessages([])}
                title="Clear chat history"
              >
                <Trash2 size={15} />
              </button>
            </>
          )}
        </header>
        
        <ChatBox 
          messages={messages} 
          isLoading={isLoading} 
          onSendMessage={handleSendMessage} 
        />
      </section>

      {/* Right Agent Trace Section */}
      <section className="glass-panel trace-section">
        <header className="header">
          <Activity size={20} color="var(--accent-purple)" />
          <h2 style={{ fontSize: '1rem' }}>Agent Audit Trace</h2>
        </header>

        <KnowledgeBase 
          refreshTrigger={kbRefresh} 
          onDocDeleted={() => setKbRefresh(prev => prev + 1)}
        />
        
        <AgentTrace 
          traceLog={latestTrace} 
          domain={latestDomain} 
        />
        
        <Uploader onUploadSuccess={(total) => {
          console.log('Vector store updated. Total chunks:', total);
          setKbRefresh(prev => prev + 1);
        }} />
      </section>

      {/* Modals */}
      <QuizModal isOpen={isQuizOpen} onClose={() => setIsQuizOpen(false)} />
      <FlashcardModal isOpen={isFlashcardsOpen} onClose={() => setIsFlashcardsOpen(false)} />
    </div>
  );
}

export default App;

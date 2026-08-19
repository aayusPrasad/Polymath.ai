import React, { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, User, Bot, FileText, Copy, Check, Sparkles, Volume2, VolumeX, Zap } from 'lucide-react';

const SUGGESTED_PROMPTS = [
  "What is Three-Address Code (3AC)?",
  "Explain Merge Sort time & space complexity",
  "What is an Abstract Syntax Tree (AST)?",
  "Difference between Paging and Segmentation",
];

export default function ChatBox({ messages, isLoading, onSendMessage }) {
  const [input, setInput] = useState('');
  const [copiedIdx, setCopiedIdx] = useState(null);
  const [speakingIdx, setSpeakingIdx] = useState(null);
  const endOfMessagesRef = useRef(null);

  useEffect(() => {
    endOfMessagesRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim());
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleCopy = (text, idx) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  const handleSpeak = (text, idx) => {
    if ('speechSynthesis' in window) {
      if (speakingIdx === idx) {
        window.speechSynthesis.cancel();
        setSpeakingIdx(null);
        return;
      }
      window.speechSynthesis.cancel(); // Stop any ongoing speech
      const plainText = text.replace(/[*#_`~]/g, ''); // Strip markdown syntax
      const utterance = new SpeechSynthesisUtterance(plainText);
      utterance.rate = 1.0;
      utterance.onend = () => setSpeakingIdx(null);
      utterance.onerror = () => setSpeakingIdx(null);
      setSpeakingIdx(idx);
      window.speechSynthesis.speak(utterance);
    }
  };

  return (
    <>
      <div className="message-list">
        {messages.length === 0 ? (
          <div className="empty-state">
            <Bot size={56} opacity={0.3} color="var(--accent-blue)" />
            <h3>Welcome to Polymath.ai</h3>
            <p>Ask any CS question or choose a suggested topic below:</p>

            <div className="suggested-chips">
              {SUGGESTED_PROMPTS.map((prompt, i) => (
                <button 
                  key={i} 
                  className="chip-btn"
                  onClick={() => onSendMessage(prompt)}
                >
                  <Sparkles size={12} color="var(--accent-purple)" />
                  <span>{prompt}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="avatar">
                {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
              </div>
              <div className="bubble">
                {msg.role === 'user' ? (
                  <p style={{ margin: 0 }}>{msg.content}</p>
                ) : (
                  <>
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                    
                    <div className="message-footer">
                      <div className="citations-time-group">
                        {msg.citations && msg.citations.length > 0 && (
                          <div className="citations">
                            {msg.citations.map((cite, i) => (
                              <span key={i} className="citation-pill" title="Source Document">
                                <FileText size={12} /> {cite}
                              </span>
                            ))}
                          </div>
                        )}
                        {msg.processingTime && (
                          <span className="latency-badge" title="Agent processing time">
                            <Zap size={11} color="#eab308" /> {msg.processingTime}s
                          </span>
                        )}
                      </div>

                      <div className="msg-actions-right">
                        {'speechSynthesis' in window && (
                          <button 
                            className={`copy-msg-btn ${speakingIdx === idx ? 'active-speech' : ''}`}
                            onClick={() => handleSpeak(msg.content, idx)}
                            title={speakingIdx === idx ? "Stop speaking" : "Listen to answer"}
                          >
                            {speakingIdx === idx ? <VolumeX size={13} color="#ef4444" /> : <Volume2 size={13} />}
                          </button>
                        )}

                        <button 
                          className="copy-msg-btn"
                          onClick={() => handleCopy(msg.content, idx)}
                          title="Copy answer to clipboard"
                        >
                          {copiedIdx === idx ? <Check size={13} color="var(--accent-green)" /> : <Copy size={13} />}
                        </button>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))
        )}

        {isLoading && (
          <div className="message assistant">
            <div className="avatar"><Bot size={20} /></div>
            <div className="bubble typing-indicator">
              <div className="dot"></div>
              <div className="dot"></div>
              <div className="dot"></div>
            </div>
          </div>
        )}
        <div ref={endOfMessagesRef} />
      </div>

      <div className="input-area">
        <form onSubmit={handleSubmit} className="input-wrapper">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a computer science question..."
            rows={1}
            disabled={isLoading}
          />
          <button type="submit" className="send-btn" disabled={!input.trim() || isLoading}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </>
  );
}

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';
import MarkdownRenderer from '../utils/MarkdownRenderer';
import { useToast } from '../context/ToastContext';
import '../styles/main.css';
import '../styles/chat.css';

const SUGGESTED_QUESTIONS = [
  "What is the groundwater level in Ananthapuramu?",
  "Compare groundwater levels in Ananthapuramu and Kurnool.",
  "Which district has the highest groundwater level?",
  "What was the rainfall percentage in Ananthapuramu?",
  "Show groundwater statistics for Andhra Pradesh.",
  "Which districts have low groundwater availability?"
];

const Assistant = () => {
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState([]);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [conversationId, setConversationId] = useState(null);
  const navigate = useNavigate();
  const { showToast } = useToast();
  
  // Ref used to auto-scroll the chat to the bottom on new messages
  const messagesEndRef = useRef(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Auto-scroll whenever messages array changes
  useEffect(() => {
    scrollToBottom();
  }, [messages, loading, scrollToBottom]);

  // Load chat query history on startup
  const fetchHistory = async () => {
    try {
      const res = await api.get('/api/ai/history');
      setHistory(res.data);
    } catch (err) {
      console.warn("Failed to load chat history logs", err);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const handleSendQuery = async (textToSend) => {
    if (!textToSend.trim()) return;
    
    // Add user message to screen
    const userMsg = { sender: 'user', text: textToSend };
    setMessages(prev => [...prev, userMsg]);
    setQuery('');
    setLoading(true);
    setError('');

    try {
      const res = await api.post('/api/ai/chat', { 
        query: textToSend,
        conversation_id: conversationId
      });
      
      if (res.data.conversation_id) {
        setConversationId(res.data.conversation_id);
      }
      
      // Add AI response to screen
      const aiMsg = {
        sender: 'ai',
        text: res.data.response,
        district_id: res.data.district_id,
        district_name: res.data.district_name
      };
      
      setMessages(prev => [...prev, aiMsg]);
      setLoading(false);
      fetchHistory(); // Refresh history panel
    } catch (err) {
      console.error(err);
      setLoading(false);
      const errorMsg = err.response?.data?.detail || "The AI service is temporarily unavailable. Please try again.";
      setError(errorMsg);
      setMessages(prev => [...prev, {
        sender: 'ai',
        text: `⚠️ **Error:** ${errorMsg}`,
        isError: true
      }]);
    }
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    handleSendQuery(query);
  };

  const handleSuggestionClick = (suggestion) => {
    handleSendQuery(suggestion);
  };

  const loadHistoryItem = (item) => {
    // Populate chat view with selected historical message exchange
    setMessages([
      { sender: 'user', text: item.query },
      { sender: 'ai', text: item.response, district_id: item.district_id }
    ]);
  };

  const handleNewChat = () => {
    setMessages([]);
    setConversationId(null);
    setQuery('');
    setError('');
  };

  const handleCopyText = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      showToast('Response copied to clipboard!', 'success');
    } catch {
      showToast('Failed to copy to clipboard.', 'error');
    }
  };

  return (
    <div className="container-inner">
      <header className="page-header" style={{ marginBottom: '15px' }}>
        <div>
          <h1 className="page-title">INGRES AI Assistant</h1>
          <p className="page-subtitle">Chat in natural language to query and compare groundwater reserves.</p>
        </div>
        {messages.length > 0 && (
          <button
            className="btn btn-outline"
            onClick={handleNewChat}
            style={{ padding: '8px 18px', fontSize: '0.88rem', gap: '6px' }}
            title="Clear current conversation and start fresh"
          >
            ✨ New Chat
          </button>
        )}
      </header>

      <div className="chat-layout">
        {/* Left Side: Conversation History list */}
        <aside className="chat-history-sidebar">
          <div className="chat-history-header">Recent Queries</div>
          <div className="chat-history-list">
            {history.length === 0 ? (
              <div className="empty-state" style={{ padding: '20px 10px', fontSize: '0.82rem' }}>
                No queries yet.
              </div>
            ) : (
              history.map((item) => (
                <div 
                  key={item.id} 
                  className="chat-history-item" 
                  onClick={() => loadHistoryItem(item)}
                  title={item.query}
                >
                  {item.query}
                </div>
              ))
            )}
          </div>
        </aside>

        {/* Right Side: Chat Dialog Area */}
        <section className="chat-main">
          <div className="chat-messages">
            {messages.length === 0 ? (
              <div style={{ margin: 'auto', textAlign: 'center', maxWidth: '500px', padding: '20px' }}>
                <div style={{ fontSize: '3rem', marginBottom: '15px' }}>🤖</div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '10px' }}>
                  Ask INGRES AI Groundwater Assistant
                </h3>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '30px' }}>
                  Ask questions about levels, recharge values, or compare districts.
                  For example: "What is the groundwater level in Ananthapuramu?"
                </p>

                {/* Grid of Suggested questions */}
                <div className="chat-suggestions-container">
                  <div className="chat-suggestions-title">Suggested Questions</div>
                  <div className="chat-suggestions-grid">
                    {SUGGESTED_QUESTIONS.map((q, idx) => (
                      <button 
                        key={idx} 
                        className="suggestion-chip"
                        onClick={() => handleSuggestionClick(q)}
                      >
                        {q}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div key={idx} className={`message ${msg.sender}`}>
                  <div className="message-bubble">
                    <div className="message-text">
                      <MarkdownRenderer text={msg.text} />
                    </div>
                    
                    {msg.sender === 'ai' && !msg.isError && (
                      <div className="message-source">
                        <span>Source: INGRES Groundwater Dataset</span>
                        <div style={{ display: 'flex', gap: '10px' }}>
                          <span className="message-source-btn" onClick={() => handleCopyText(msg.text)}>
                            📋 Copy
                          </span>
                          <span className="message-source-btn" onClick={() => showToast('Thank you for your feedback!', 'success')}>
                            👍 Feedback
                          </span>
                          {msg.district_id && (
                            <span 
                              className="message-source-btn" 
                              style={{ color: 'var(--secondary-color)' }}
                              onClick={() => navigate(`/districts/${msg.district_id}`)}
                            >
                              🔍 View Details
                            </span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            
            {loading && (
              <div className="message ai">
                <div className="message-bubble" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{
                    width: '18px',
                    height: '18px',
                    border: '2.5px solid var(--border-color)',
                    borderTopColor: 'var(--primary-color)',
                    borderRadius: '50%',
                    animation: 'spin 1s linear infinite'
                  }}></div>
                  <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Generating AI response...</span>
                </div>
              </div>
            )}

            {/* Invisible anchor element for auto-scroll */}
            <div ref={messagesEndRef} />
          </div>

          {/* Bottom Chat Input Form */}
          <div className="chat-input-container">
            <form onSubmit={handleFormSubmit} className="chat-input-form">
              <button type="button" className="chat-mic-btn" title="Voice search placeholder">
                🎤
              </button>
              
              <input
                type="text"
                className="chat-input-field"
                placeholder="Ask about district groundwater, e.g. What is the level in Kurnool?"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                disabled={loading}
                autoComplete="off"
              />
              
              <button 
                type="submit" 
                className="chat-input-btn"
                disabled={loading || !query.trim()}
                title="Send query"
              >
                ➔
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Assistant;

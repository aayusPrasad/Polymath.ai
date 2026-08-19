import React, { useState } from 'react';
import { Layers, RefreshCw, X, RotateCw, ChevronLeft, ChevronRight } from 'lucide-react';
import { generateFlashcards } from '../services/api';

export default function FlashcardModal({ isOpen, onClose }) {
  const [domain, setDomain] = useState('compiler_theory');
  const [loading, setLoading] = useState(false);
  const [cards, setCards] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isFlipped, setIsFlipped] = useState(false);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setLoading(true);
    setCards([]);
    setCurrentIndex(0);
    setIsFlipped(false);
    try {
      const data = await generateFlashcards(domain);
      setCards(data.cards || []);
    } catch (err) {
      alert(`Flashcard Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleNext = () => {
    setIsFlipped(false);
    setCurrentIndex((prev) => (prev + 1) % cards.length);
  };

  const handlePrev = () => {
    setIsFlipped(false);
    setCurrentIndex((prev) => (prev - 1 + cards.length) % cards.length);
  };

  const currentCard = cards[currentIndex];

  return (
    <div className="modal-overlay">
      <div className="quiz-modal glass-panel flashcard-modal">
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Layers size={20} color="var(--accent-teal)" />
            <h3>AI Study Flashcards</h3>
          </div>
          <button className="icon-btn-subtle" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="quiz-controls">
          <label>Subject:</label>
          <select value={domain} onChange={(e) => setDomain(e.target.value)} disabled={loading}>
            <option value="compiler_theory">⚙️ Compiler Theory</option>
            <option value="algorithms">📊 Algorithms & Data Structures</option>
            <option value="theory_of_comp">🧮 Theory of Computation</option>
            <option value="general_cs">🖥️ General Computer Science</option>
          </select>
          <button className="quiz-gen-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? <RefreshCw className="spin-icon" size={16} /> : <Layers size={16} />}
            {loading ? 'Generating...' : 'Create Flashcards'}
          </button>
        </div>

        <div className="quiz-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          {cards.length === 0 && !loading && (
            <div className="empty-quiz">
              <Layers size={48} opacity={0.3} />
              <p>Select a subject and click <strong>Create Flashcards</strong> to test your recall!</p>
            </div>
          )}

          {loading && (
            <div className="empty-quiz">
              <RefreshCw className="spin-icon" size={40} color="var(--accent-teal)" />
              <p>Polymath Agents are generating concept cards...</p>
            </div>
          )}

          {currentCard && (
            <div className="flashcard-deck">
              <div 
                className={`flashcard-scene ${isFlipped ? 'flipped' : ''}`}
                onClick={() => setIsFlipped(!isFlipped)}
              >
                <div className="flashcard-inner">
                  <div className="flashcard-face flashcard-front">
                    <span className="card-badge">Card {currentIndex + 1} of {cards.length} — FRONT</span>
                    <p className="card-text">{currentCard.front}</p>
                    <span className="flip-hint"><RotateCw size={14} /> Click to flip</span>
                  </div>
                  <div className="flashcard-face flashcard-back">
                    <span className="card-badge">Card {currentIndex + 1} of {cards.length} — BACK</span>
                    <p className="card-text">{currentCard.back}</p>
                    <span className="flip-hint"><RotateCw size={14} /> Click to flip</span>
                  </div>
                </div>
              </div>

              <div className="flashcard-nav">
                <button className="action-btn-header" onClick={handlePrev}>
                  <ChevronLeft size={16} /> Previous
                </button>
                <span className="nav-counter">{currentIndex + 1} / {cards.length}</span>
                <button className="action-btn-header" onClick={handleNext}>
                  Next <ChevronRight size={16} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

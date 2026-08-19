import React, { useState } from 'react';
import { HelpCircle, CheckCircle, XCircle, RefreshCw, X, Award } from 'lucide-react';
import { generateQuiz } from '../services/api';

export default function QuizModal({ isOpen, onClose }) {
  const [domain, setDomain] = useState('general_cs');
  const [loading, setLoading] = useState(false);
  const [quiz, setQuiz] = useState(null);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const handleGenerate = async () => {
    setLoading(true);
    setQuiz(null);
    setSelectedAnswers({});
    setSubmitted(false);
    try {
      const data = await generateQuiz(domain);
      setQuiz(data);
    } catch (err) {
      alert(`Quiz Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (questionId, optionIdx) => {
    if (submitted) return;
    setSelectedAnswers(prev => ({ ...prev, [questionId]: optionIdx }));
  };

  const calculateScore = () => {
    if (!quiz) return 0;
    let score = 0;
    quiz.questions.forEach(q => {
      if (selectedAnswers[q.id] === q.answer_index) score += 1;
    });
    return score;
  };

  return (
    <div className="modal-overlay">
      <div className="quiz-modal glass-panel">
        <div className="modal-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Award size={20} color="var(--accent-purple)" />
            <h3>AI Practice Quiz Generator</h3>
          </div>
          <button className="icon-btn-subtle" onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        <div className="quiz-controls">
          <label>Select CS Subject:</label>
          <select value={domain} onChange={(e) => setDomain(e.target.value)} disabled={loading}>
            <option value="compiler_theory">⚙️ Compiler Theory</option>
            <option value="algorithms">📊 Algorithms & Data Structures</option>
            <option value="theory_of_comp">🧮 Theory of Computation</option>
            <option value="general_cs">🖥️ General Computer Science</option>
          </select>
          <button className="quiz-gen-btn" onClick={handleGenerate} disabled={loading}>
            {loading ? <RefreshCw className="spin-icon" size={16} /> : <HelpCircle size={16} />}
            {loading ? 'Generating...' : 'Generate Quiz'}
          </button>
        </div>

        <div className="quiz-body">
          {!quiz && !loading && (
            <div className="empty-quiz">
              <HelpCircle size={48} opacity={0.3} />
              <p>Select a subject and click <strong>Generate Quiz</strong> to test your CS knowledge!</p>
            </div>
          )}

          {loading && (
            <div className="empty-quiz">
              <RefreshCw className="spin-icon" size={40} color="var(--accent-blue)" />
              <p>Polymath Agents are creating your quiz...</p>
            </div>
          )}

          {quiz && (
            <div className="quiz-questions-list">
              {quiz.questions.map((q, idx) => {
                const userChoice = selectedAnswers[q.id];
                const isCorrect = userChoice === q.answer_index;

                return (
                  <div key={q.id} className="quiz-q-card">
                    <h4>Q{idx + 1}. {q.question}</h4>
                    <div className="quiz-options">
                      {q.options.map((opt, optIdx) => {
                        let optClass = 'quiz-opt';
                        if (userChoice === optIdx) optClass += ' selected';
                        if (submitted) {
                          if (optIdx === q.answer_index) optClass += ' correct';
                          else if (userChoice === optIdx) optClass += ' incorrect';
                        }
                        return (
                          <button
                            key={optIdx}
                            className={optClass}
                            onClick={() => handleSelect(q.id, optIdx)}
                          >
                            <span className="opt-letter">{String.fromCharCode(65 + optIdx)}.</span> {opt}
                          </button>
                        );
                      })}
                    </div>

                    {submitted && (
                      <div className={`quiz-explanation ${isCorrect ? 'correct' : 'incorrect'}`}>
                        {isCorrect ? <CheckCircle size={16} /> : <XCircle size={16} />}
                        <div>
                          <strong>{isCorrect ? 'Correct!' : 'Incorrect.'}</strong> {q.explanation}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              {!submitted ? (
                <button
                  className="quiz-submit-btn"
                  onClick={() => setSubmitted(true)}
                  disabled={Object.keys(selectedAnswers).length < quiz.questions.length}
                >
                  Submit Answers
                </button>
              ) : (
                <div className="quiz-results-banner">
                  🎉 Score: {calculateScore()} / {quiz.questions.length}
                  <button className="quiz-gen-btn" style={{ marginLeft: '1rem' }} onClick={handleGenerate}>
                    Try Another Quiz
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

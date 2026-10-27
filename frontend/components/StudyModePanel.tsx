"use client";

import React, { useState, useEffect } from 'react';
import { getDueFlashcards, reviewFlashcard, Flashcard } from '../lib/api';

export default function StudyModePanel() {
  const [cards, setCards] = useState<Flashcard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [showAnswer, setShowAnswer] = useState(false);
  const [reviewing, setReviewing] = useState(false);

  useEffect(() => {
    fetchCards();
  }, []);

  async function fetchCards() {
    setLoading(true);
    setError(null);
    try {
      const dueCards = await getDueFlashcards();
      setCards(dueCards || []);
      setCurrentIndex(0);
      setShowAnswer(false);
    } catch (err: any) {
      setError(err.message || 'Failed to load due flashcards');
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(score: number) {
    if (cards.length === 0 || reviewing) return;
    
    setReviewing(true);
    const currentCard = cards[currentIndex];
    try {
      await reviewFlashcard(currentCard.id, score);
      // Move to next
      if (currentIndex < cards.length - 1) {
        setCurrentIndex(prev => prev + 1);
        setShowAnswer(false);
      } else {
        // Done with the session, fetch again to ensure empty or new ones
        await fetchCards();
      }
    } catch (err: any) {
      setError(err.message || 'Failed to submit review');
    } finally {
      setReviewing(false);
    }
  }

  if (loading) return (
    <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
      Loading flashcards...
    </div>
  );
  if (error) return <div style={{ color: 'var(--status-error-text)', padding: '2rem', textAlign: 'center' }}>{error}</div>;
  if (cards.length === 0) return (
    <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
      <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎉</div>
      <h2 style={{ color: 'var(--text-primary)', marginBottom: '0.5rem' }}>You're all caught up!</h2>
      <p>No flashcards due for review right now. Come back later.</p>
    </div>
  );

  const card = cards[currentIndex];
  const progress = ((currentIndex) / cards.length) * 100;

  return (
    <div style={{ maxWidth: '680px', margin: '0 auto', padding: '2rem' }}>
      {/* Progress bar */}
      <div style={{ marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          <span>Card {currentIndex + 1} of {cards.length}</span>
          <span>{Math.round(progress)}% complete</span>
        </div>
        <div style={{ height: '4px', backgroundColor: 'var(--surface-light)', borderRadius: '9999px', overflow: 'hidden' }}>
          <div style={{ height: '100%', width: `${progress}%`, background: 'var(--accent-gradient)', borderRadius: '9999px', transition: 'width 0.3s ease' }} />
        </div>
      </div>

      {/* Flashcard */}
      <div className="glass-card" style={{
        borderRadius: '1rem',
        padding: '3rem 2.5rem',
        minHeight: '280px',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        textAlign: 'center',
        transition: 'all 0.3s ease',
        position: 'relative'
      }}>
        {/* Subtle glow behind card */}
        <div style={{ position: 'absolute', inset: 0, background: 'radial-gradient(circle at 50% 30%, rgba(59,130,246,0.05), transparent 70%)', borderRadius: '1rem', pointerEvents: 'none' }} />

        <div style={{ fontSize: '1.3rem', fontWeight: 600, color: 'var(--text-primary)', lineHeight: '1.6', marginBottom: showAnswer ? '2rem' : 0, zIndex: 1 }}>
          {card.front}
        </div>

        {showAnswer && (
          <div style={{
            fontSize: '1.05rem',
            color: 'var(--text-secondary)',
            borderTop: '1px dashed var(--border-color)',
            paddingTop: '1.5rem',
            width: '100%',
            lineHeight: '1.6',
            zIndex: 1
          }}>
            {card.back}
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div style={{ marginTop: '1.5rem', display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        {!showAnswer ? (
          <button
            onClick={() => setShowAnswer(true)}
            className="btn-primary"
            style={{ padding: '0.875rem 2.5rem', borderRadius: '2rem', fontSize: '1rem' }}
          >
            Reveal Answer
          </button>
        ) : (
          <>
            <button
              onClick={() => handleReview(1)}
              disabled={reviewing}
              style={{ padding: '0.75rem 1.25rem', background: 'rgba(239,68,68,0.15)', color: '#f87171', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '0.5rem', cursor: 'pointer', fontWeight: 600, transition: 'all 0.2s' }}
            >
              😓 Hard
            </button>
            <button
              onClick={() => handleReview(2)}
              disabled={reviewing}
              style={{ padding: '0.75rem 1.25rem', background: 'rgba(245,158,11,0.15)', color: '#fbbf24', border: '1px solid rgba(245,158,11,0.3)', borderRadius: '0.5rem', cursor: 'pointer', fontWeight: 600, transition: 'all 0.2s' }}
            >
              🤔 Okay
            </button>
            <button
              onClick={() => handleReview(3)}
              disabled={reviewing}
              className="btn-primary"
              style={{ padding: '0.75rem 1.25rem', borderRadius: '0.5rem' }}
            >
              👍 Good
            </button>
            <button
              onClick={() => handleReview(4)}
              disabled={reviewing}
              style={{ padding: '0.75rem 1.25rem', background: 'rgba(34,197,94,0.15)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)', borderRadius: '0.5rem', cursor: 'pointer', fontWeight: 600, transition: 'all 0.2s' }}
            >
              🚀 Easy
            </button>
          </>
        )}
      </div>
    </div>
  );
}

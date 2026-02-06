import { useState, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, Send, Sparkles } from 'lucide-react';
import { useAppState } from '../hooks/useAppState';
import ReputationBadge from '../components/reputation/ReputationBadge';
import ReputationLens from '../components/reputation/ReputationLens';
import './ChatPage.css';

export default function ChatPage() {
  const { matchId } = useParams<{ matchId: string }>();
  const navigate = useNavigate();
  const { matches, getProfile, getConversation, sendMessage } = useAppState();
  const [input, setInput] = useState('');
  const [showLens, setShowLens] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const match = matches.find(m => m.id === matchId);
  const otherUserId = match?.users.find(u => u !== 'user-me');
  const profile = otherUserId ? getProfile(otherUserId) : undefined;
  const conversation = matchId ? getConversation(matchId) : undefined;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation?.messages.length]);

  if (!match || !profile) {
    return (
      <div className="chat-error">
        <p>Match not found</p>
        <button onClick={() => navigate('/matches')}>Back to Matches</button>
      </div>
    );
  }

  const handleSend = () => {
    if (!input.trim() || !conversation) return;
    sendMessage(conversation.id, input.trim());
    setInput('');
  };

  const formatMessageTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const formatDateSeparator = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffDays = Math.floor((now.getTime() - date.getTime()) / 86400000);

    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
  };

  // Group messages by date
  const messageGroups: { date: string; messages: typeof conversation.messages }[] = [];
  conversation?.messages.forEach(msg => {
    const dateKey = new Date(msg.timestamp).toDateString();
    const existing = messageGroups.find(g => g.date === dateKey);
    if (existing) {
      existing.messages.push(msg);
    } else {
      messageGroups.push({ date: dateKey, messages: [msg] });
    }
  });

  return (
    <div className="chat-page">
      {/* Header */}
      <header className="chat-header">
        <button className="chat-header__back" onClick={() => navigate('/matches')}>
          <ArrowLeft size={22} />
        </button>

        <button className="chat-header__profile" onClick={() => setShowLens(true)}>
          <img src={profile.photos[0].url} alt={profile.firstName} className="chat-header__avatar" />
          <div className="chat-header__info">
            <span className="chat-header__name">{profile.firstName}</span>
            <ReputationBadge reputation={profile.reputation} size="sm" showLabel />
          </div>
        </button>

        <button className="chat-header__lens" onClick={() => setShowLens(true)}>
          <Sparkles size={18} />
        </button>
      </header>

      {/* Messages */}
      <div className="chat-messages">
        {/* Match context */}
        <div className="chat-match-context">
          <img src={profile.photos[0].url} alt={profile.firstName} className="chat-match-context__avatar" />
          <p className="chat-match-context__text">
            You matched with <strong>{profile.firstName}</strong>
          </p>
          {match.like.comment && (
            <div className="chat-match-context__like">
              <span className="chat-match-context__like-label">
                {match.like.fromUserId === 'user-me' ? 'You' : profile.firstName} commented on a prompt
              </span>
              <p>"{match.like.comment}"</p>
            </div>
          )}
        </div>

        {messageGroups.map(group => (
          <div key={group.date}>
            <div className="chat-date-sep">
              <span>{formatDateSeparator(group.messages[0].timestamp)}</span>
            </div>

            {group.messages.map((msg, i) => {
              const isMe = msg.senderId === 'user-me';
              const showAvatar = !isMe && (i === 0 || group.messages[i - 1]?.senderId !== msg.senderId);

              return (
                <motion.div
                  key={msg.id}
                  className={`chat-bubble-row ${isMe ? 'chat-bubble-row--me' : 'chat-bubble-row--them'}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.15 }}
                >
                  {!isMe && showAvatar && (
                    <img src={profile.photos[0].url} alt="" className="chat-bubble__avatar" />
                  )}
                  {!isMe && !showAvatar && <div className="chat-bubble__avatar-spacer" />}

                  <div className={`chat-bubble ${isMe ? 'chat-bubble--me' : 'chat-bubble--them'} ${msg.type === 'opener' ? 'chat-bubble--opener' : ''}`}>
                    <p>{msg.content}</p>
                    <span className="chat-bubble__time">{formatMessageTime(msg.timestamp)}</span>
                  </div>
                </motion.div>
              );
            })}
          </div>
        ))}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-bar">
        <input
          type="text"
          className="chat-input"
          placeholder="Say something thoughtful..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
        />
        <button
          className="chat-send-btn"
          onClick={handleSend}
          disabled={!input.trim()}
        >
          <Send size={18} />
        </button>
      </div>

      {/* Reputation Lens */}
      <ReputationLens
        profile={profile}
        isOpen={showLens}
        onClose={() => setShowLens(false)}
      />
    </div>
  );
}

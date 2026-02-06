import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { MessageSquare, Clock, Sparkles } from 'lucide-react';
import { useAppState } from '../hooks/useAppState';
import ReputationBadge from '../components/reputation/ReputationBadge';
import ReputationLens from '../components/reputation/ReputationLens';
import type { UserProfile } from '../types';
import './MatchesPage.css';

export default function MatchesPage() {
  const { matches, conversations, getProfile } = useAppState();
  const navigate = useNavigate();
  const [lensProfile, setLensProfile] = useState<UserProfile | null>(null);

  const activeConvos = matches
    .filter(m => m.status === 'matched')
    .map(match => {
      const otherUserId = match.users.find(u => u !== 'user-me')!;
      const profile = getProfile(otherUserId);
      const convo = conversations.find(c => c.matchId === match.id);
      const lastMessage = convo?.messages[convo.messages.length - 1];

      return { match, profile, convo, lastMessage };
    })
    .filter(item => item.profile);

  const withConvos = activeConvos.filter(c => c.convo && c.convo.messages.length > 0);
  const newMatches = activeConvos.filter(c => !c.convo || c.convo.messages.length === 0);

  const formatTime = (timestamp: string) => {
    const diff = Date.now() - new Date(timestamp).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h`;
    const days = Math.floor(hrs / 24);
    return `${days}d`;
  };

  return (
    <div className="matches-page">
      <header className="matches-header">
        <h1>Matches</h1>
        <span className="matches-count">{activeConvos.length}</span>
      </header>

      {/* New Matches (no conversation yet) */}
      {newMatches.length > 0 && (
        <section className="matches-section">
          <h2 className="matches-section__title">
            <Sparkles size={14} />
            New Matches
          </h2>
          <div className="new-matches-scroll">
            {newMatches.map(({ match, profile }, i) => (
              <motion.button
                key={match.id}
                className="new-match-card"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.1 }}
                onClick={() => navigate(`/chat/${match.id}`)}
              >
                <div className="new-match-card__avatar">
                  <img src={profile!.photos[0].url} alt={profile!.firstName} />
                  <ReputationBadge
                    reputation={profile!.reputation}
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      setLensProfile(profile!);
                    }}
                  />
                </div>
                <span className="new-match-card__name">{profile!.firstName}</span>
              </motion.button>
            ))}
          </div>
        </section>
      )}

      {/* Active Conversations */}
      <section className="matches-section">
        <h2 className="matches-section__title">
          <MessageSquare size={14} />
          Conversations
        </h2>

        {withConvos.length === 0 ? (
          <div className="matches-empty">
            <p>No conversations yet. Send the first message!</p>
          </div>
        ) : (
          <div className="convo-list">
            {withConvos.map(({ match, profile, lastMessage }, i) => {
              const isUnread = match.hasUnread || (lastMessage && !lastMessage.read && lastMessage.senderId !== 'user-me');
              return (
                <motion.button
                  key={match.id}
                  className={`convo-item ${isUnread ? 'convo-item--unread' : ''}`}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  onClick={() => navigate(`/chat/${match.id}`)}
                >
                  <div className="convo-item__avatar">
                    <img src={profile!.photos[0].url} alt={profile!.firstName} />
                    {isUnread && <span className="convo-item__unread-dot" />}
                  </div>

                  <div className="convo-item__content">
                    <div className="convo-item__top">
                      <span className="convo-item__name">
                        {profile!.firstName}
                        <ReputationBadge
                          reputation={profile!.reputation}
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            setLensProfile(profile!);
                          }}
                        />
                      </span>
                      {lastMessage && (
                        <span className="convo-item__time">
                          <Clock size={11} />
                          {formatTime(lastMessage.timestamp)}
                        </span>
                      )}
                    </div>
                    {lastMessage && (
                      <p className="convo-item__preview">
                        {lastMessage.senderId === 'user-me' ? 'You: ' : ''}
                        {lastMessage.content}
                      </p>
                    )}
                  </div>
                </motion.button>
              );
            })}
          </div>
        )}
      </section>

      {/* Reputation Lens */}
      {lensProfile && (
        <ReputationLens
          profile={lensProfile}
          isOpen={!!lensProfile}
          onClose={() => setLensProfile(null)}
        />
      )}
    </div>
  );
}

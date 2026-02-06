import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Heart, MessageSquare, ChevronDown, MapPin, Briefcase, GraduationCap, Ruler } from 'lucide-react';
import { useAppState } from '../hooks/useAppState';
import ReputationBadge from '../components/reputation/ReputationBadge';
import ReputationLens from '../components/reputation/ReputationLens';
import './DiscoverPage.css';

export default function DiscoverPage() {
  const { discoverQueue, currentDiscoverIndex, passProfile, likeProfile } = useAppState();
  const [showLens, setShowLens] = useState(false);
  const [commentMode, setCommentMode] = useState<{ promptIndex: number } | null>(null);
  const [commentText, setCommentText] = useState('');
  const [exitDirection, setExitDirection] = useState<'left' | 'right' | null>(null);

  const profile = discoverQueue[currentDiscoverIndex];

  if (!profile) {
    return (
      <div className="discover-empty">
        <div className="discover-empty__icon">✦</div>
        <h2>You're all caught up</h2>
        <p>Check back later for new profiles. Quality over quantity.</p>
      </div>
    );
  }

  const handlePass = () => {
    setExitDirection('left');
    setTimeout(() => {
      passProfile();
      setExitDirection(null);
    }, 300);
  };

  const handleLike = () => {
    setExitDirection('right');
    setTimeout(() => {
      likeProfile();
      setExitDirection(null);
    }, 300);
  };

  const handleComment = () => {
    if (commentMode && commentText.trim()) {
      setExitDirection('right');
      setTimeout(() => {
        likeProfile(commentText.trim(), commentMode.promptIndex);
        setCommentMode(null);
        setCommentText('');
        setExitDirection(null);
      }, 300);
    }
  };

  return (
    <div className="discover">
      {/* Header */}
      <header className="discover-header">
        <h1 className="discover-header__logo">momentum</h1>
      </header>

      {/* Card */}
      <AnimatePresence mode="wait">
        <motion.div
          key={profile.id}
          className="profile-card"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{
            opacity: exitDirection ? 0 : 1,
            scale: exitDirection ? 0.9 : 1,
            x: exitDirection === 'left' ? -300 : exitDirection === 'right' ? 300 : 0,
            rotate: exitDirection === 'left' ? -15 : exitDirection === 'right' ? 15 : 0,
          }}
          transition={{ duration: 0.3, ease: 'easeOut' }}
        >
          {/* Photo Section */}
          <div className="profile-card__photo">
            <img src={profile.photos[0].url} alt={profile.firstName} />
            <div className="profile-card__photo-overlay" />

            {/* Name & basics on photo */}
            <div className="profile-card__photo-info">
              <div className="profile-card__name-row">
                <h2>{profile.firstName}, {profile.age}</h2>
                <ReputationBadge
                  reputation={profile.reputation}
                  size="md"
                  showLabel
                  onClick={() => setShowLens(true)}
                />
              </div>
              <div className="profile-card__location">
                <MapPin size={14} />
                <span>{profile.location}</span>
              </div>
            </div>

            <button className="profile-card__scroll-hint">
              <ChevronDown size={20} />
            </button>
          </div>

          {/* Details Section */}
          <div className="profile-card__details">
            {/* Quick Info Pills */}
            <div className="profile-card__pills">
              <span className="pill">
                <Briefcase size={13} />
                {profile.occupation}
                {profile.company && ` at ${profile.company}`}
              </span>
              {profile.education && (
                <span className="pill">
                  <GraduationCap size={13} />
                  {profile.education}
                </span>
              )}
              {profile.height && (
                <span className="pill">
                  <Ruler size={13} />
                  {profile.height}
                </span>
              )}
            </div>

            {/* Bio */}
            <p className="profile-card__bio">{profile.bio}</p>

            {/* Prompts — the Hinge signature */}
            {profile.prompts.map((prompt, idx) => (
              <div key={idx} className="prompt-card">
                <span className="prompt-card__question">{prompt.question}</span>
                <p className="prompt-card__answer">{prompt.answer}</p>
                <button
                  className="prompt-card__comment-btn"
                  onClick={() => {
                    setCommentMode({ promptIndex: idx });
                    setCommentText('');
                  }}
                >
                  <MessageSquare size={16} />
                </button>
              </div>
            ))}

            {/* Interests */}
            <div className="profile-card__interests">
              {profile.interests.map(interest => (
                <span key={interest} className="interest-chip">{interest}</span>
              ))}
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Action Buttons */}
      {!commentMode && (
        <div className="discover-actions">
          <button className="action-btn action-btn--pass" onClick={handlePass}>
            <X size={28} strokeWidth={2.5} />
          </button>
          <button className="action-btn action-btn--like" onClick={handleLike}>
            <Heart size={28} strokeWidth={2.5} />
          </button>
        </div>
      )}

      {/* Comment Input */}
      {commentMode && (
        <motion.div
          className="comment-bar"
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
        >
          <input
            type="text"
            className="comment-bar__input"
            placeholder={`Reply to "${profile.prompts[commentMode.promptIndex].question}"...`}
            value={commentText}
            onChange={e => setCommentText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleComment()}
            autoFocus
          />
          <button
            className="comment-bar__send"
            onClick={handleComment}
            disabled={!commentText.trim()}
          >
            Send
          </button>
          <button
            className="comment-bar__cancel"
            onClick={() => setCommentMode(null)}
          >
            <X size={18} />
          </button>
        </motion.div>
      )}

      {/* Reputation Lens Sheet */}
      <ReputationLens
        profile={profile}
        isOpen={showLens}
        onClose={() => setShowLens(false)}
      />
    </div>
  );
}

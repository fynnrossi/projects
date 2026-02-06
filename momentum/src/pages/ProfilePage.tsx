import { useState } from 'react';
import { motion } from 'framer-motion';
import { Settings, Shield, Edit3, Camera, Clock, MessageCircle, Send, Target, Sparkles, TrendingUp } from 'lucide-react';
import { useAppState } from '../hooks/useAppState';
import { getTierInfo, formatMetricLabel, formatMetricDescription, TIERS } from '../engine/reputation';
import type { ReputationMetrics } from '../types';
import './ProfilePage.css';

const metricIcons: Record<keyof ReputationMetrics, typeof Clock> = {
  openingLineRate: Send,
  conversationCommitment: MessageCircle,
  responsiveness: Clock,
  thoughtfulSwipeRatio: Target,
  conversationDepth: Sparkles,
};

export default function ProfilePage() {
  const { currentUser } = useAppState();
  const [activeTab, setActiveTab] = useState<'reputation' | 'profile'>('reputation');

  const { reputation } = currentUser;
  const tier = getTierInfo(reputation.tier);
  const nextTier = TIERS.find(t => t.minScore > reputation.overall);

  return (
    <div className="profile-page">
      {/* Header */}
      <header className="profile-header">
        <h1>Profile</h1>
        <div className="profile-header__actions">
          <button className="profile-header__btn">
            <Settings size={20} />
          </button>
        </div>
      </header>

      {/* User Card */}
      <div className="profile-user-card">
        <div className="profile-user-card__avatar-wrap">
          <img src={currentUser.photos[0].url} alt={currentUser.firstName} className="profile-user-card__avatar" />
          <button className="profile-user-card__edit-photo">
            <Camera size={14} />
          </button>
        </div>
        <h2>{currentUser.firstName}, {currentUser.age}</h2>
        <p className="profile-user-card__occupation">
          {currentUser.occupation}
          {currentUser.company && ` at ${currentUser.company}`}
        </p>
        <div className="profile-user-card__badge-row">
          <div
            className="profile-tier-badge"
            style={{ '--tier-color': tier.color } as React.CSSProperties}
          >
            <span className="profile-tier-badge__icon">{tier.icon}</span>
            <span className="profile-tier-badge__label">{tier.label}</span>
            <span className="profile-tier-badge__score">{reputation.overall}</span>
          </div>
          {currentUser.verified && (
            <div className="profile-verified">
              <Shield size={14} />
              Verified
            </div>
          )}
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="profile-tabs">
        <button
          className={`profile-tab ${activeTab === 'reputation' ? 'profile-tab--active' : ''}`}
          onClick={() => setActiveTab('reputation')}
        >
          <TrendingUp size={16} />
          Momentum
        </button>
        <button
          className={`profile-tab ${activeTab === 'profile' ? 'profile-tab--active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          <Edit3 size={16} />
          My Profile
        </button>
      </div>

      {activeTab === 'reputation' ? (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="profile-reputation"
        >
          {/* Score Visualization */}
          <div className="rep-dashboard__score-card">
            <div className="rep-dashboard__ring-container">
              <svg viewBox="0 0 140 140" className="rep-dashboard__ring">
                <circle cx="70" cy="70" r="58" fill="none" stroke="rgba(0,0,0,0.05)" strokeWidth="10" />
                <circle
                  cx="70" cy="70" r="58" fill="none"
                  stroke={tier.color}
                  strokeWidth="10"
                  strokeLinecap="round"
                  strokeDasharray={`${(reputation.overall / 100) * 364} 364`}
                  transform="rotate(-90 70 70)"
                  style={{ transition: 'stroke-dasharray 1s ease-out' }}
                />
              </svg>
              <div className="rep-dashboard__ring-inner">
                <span className="rep-dashboard__score-num">{reputation.overall}</span>
                <span className="rep-dashboard__score-label">Momentum</span>
              </div>
            </div>

            {nextTier && (
              <div className="rep-dashboard__next-tier">
                <span>{nextTier.icon}</span>
                <span>{nextTier.minScore - reputation.overall} points to {nextTier.label}</span>
              </div>
            )}
          </div>

          {/* Tier Progress Bar */}
          <div className="rep-dashboard__tiers">
            <div className="rep-dashboard__tier-track">
              {TIERS.map((t, i) => (
                <div
                  key={t.tier}
                  className="rep-dashboard__tier-seg"
                  style={{
                    left: `${t.minScore}%`,
                    width: `${(TIERS[i + 1]?.minScore ?? 100) - t.minScore}%`,
                    background: reputation.overall >= t.minScore ? t.color : 'rgba(0,0,0,0.06)',
                    opacity: reputation.overall >= t.minScore ? 1 : 0.3,
                  }}
                />
              ))}
              <div
                className="rep-dashboard__tier-marker"
                style={{ left: `${Math.min(reputation.overall, 98)}%` }}
              />
            </div>
            <div className="rep-dashboard__tier-labels">
              {TIERS.map(t => (
                <div key={t.tier} className="rep-dashboard__tier-label" style={{ color: t.color }}>
                  <span>{t.icon}</span>
                  <span>{t.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Stats Row */}
          <div className="rep-dashboard__stats">
            <div className="rep-stat-card">
              <span className="rep-stat-card__num">{reputation.matchesTotal}</span>
              <span className="rep-stat-card__label">Total Matches</span>
            </div>
            <div className="rep-stat-card">
              <span className="rep-stat-card__num">{reputation.conversationsStarted}</span>
              <span className="rep-stat-card__label">Convos Started</span>
            </div>
            <div className="rep-stat-card">
              <span className="rep-stat-card__num">{reputation.avgMessagesPerConvo}</span>
              <span className="rep-stat-card__label">Avg Msgs/Convo</span>
            </div>
          </div>

          {/* Detailed Metrics */}
          <div className="rep-dashboard__metrics">
            <h3 className="rep-dashboard__section-title">Your Conversation Style</h3>
            {(Object.keys(reputation.metrics) as (keyof ReputationMetrics)[]).map((key, i) => {
              const value = reputation.metrics[key];
              const Icon = metricIcons[key];
              const color = value >= 0.7 ? 'var(--accent-success)' :
                value >= 0.4 ? 'var(--accent-warm)' : 'var(--accent-secondary)';

              return (
                <motion.div
                  key={key}
                  className="rep-metric-row"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.1 }}
                >
                  <div className="rep-metric-row__icon" style={{ background: `${color}15`, color }}>
                    <Icon size={16} />
                  </div>
                  <div className="rep-metric-row__body">
                    <div className="rep-metric-row__header">
                      <span className="rep-metric-row__name">{formatMetricLabel(key)}</span>
                      <span className="rep-metric-row__pct" style={{ color }}>{Math.round(value * 100)}%</span>
                    </div>
                    <div className="rep-metric-row__bar">
                      <motion.div
                        className="rep-metric-row__fill"
                        initial={{ width: 0 }}
                        animate={{ width: `${value * 100}%` }}
                        transition={{ duration: 0.8, delay: i * 0.1 }}
                        style={{ background: color }}
                      />
                    </div>
                    <span className="rep-metric-row__desc">{formatMetricDescription(key)}</span>
                  </div>
                </motion.div>
              );
            })}
          </div>

          {/* Tips */}
          <div className="rep-dashboard__tips">
            <h3 className="rep-dashboard__section-title">Boost Your Momentum</h3>
            <div className="rep-tip">
              <Send size={15} />
              <div>
                <strong>Send the first message</strong>
                <p>People who open conversations match 3x more often</p>
              </div>
            </div>
            <div className="rep-tip">
              <MessageCircle size={15} />
              <div>
                <strong>Ask a follow-up question</strong>
                <p>Conversations with questions last 2x longer</p>
              </div>
            </div>
            <div className="rep-tip">
              <Target size={15} />
              <div>
                <strong>Be selective</strong>
                <p>Thoughtful swiping leads to more meaningful matches</p>
              </div>
            </div>
          </div>
        </motion.div>
      ) : (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="profile-details"
        >
          {/* Bio */}
          <div className="profile-section">
            <div className="profile-section__header">
              <h3>About Me</h3>
              <button className="profile-edit-btn"><Edit3 size={14} /></button>
            </div>
            <p className="profile-section__text">{currentUser.bio}</p>
          </div>

          {/* Prompts */}
          <div className="profile-section">
            <div className="profile-section__header">
              <h3>My Prompts</h3>
              <button className="profile-edit-btn"><Edit3 size={14} /></button>
            </div>
            {currentUser.prompts.map((prompt, idx) => (
              <div key={idx} className="profile-prompt">
                <span className="profile-prompt__q">{prompt.question}</span>
                <p className="profile-prompt__a">{prompt.answer}</p>
              </div>
            ))}
          </div>

          {/* Interests */}
          <div className="profile-section">
            <div className="profile-section__header">
              <h3>Interests</h3>
              <button className="profile-edit-btn"><Edit3 size={14} /></button>
            </div>
            <div className="profile-interests-grid">
              {currentUser.interests.map(interest => (
                <span key={interest} className="profile-interest-chip">{interest}</span>
              ))}
            </div>
          </div>

          {/* Quick Info */}
          <div className="profile-section">
            <div className="profile-section__header">
              <h3>Details</h3>
            </div>
            <div className="profile-detail-list">
              <div className="profile-detail-item">
                <span className="profile-detail-item__label">Location</span>
                <span>{currentUser.location}</span>
              </div>
              {currentUser.height && (
                <div className="profile-detail-item">
                  <span className="profile-detail-item__label">Height</span>
                  <span>{currentUser.height}</span>
                </div>
              )}
              {currentUser.education && (
                <div className="profile-detail-item">
                  <span className="profile-detail-item__label">Education</span>
                  <span>{currentUser.education}</span>
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

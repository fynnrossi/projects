import { motion, AnimatePresence } from 'framer-motion';
import { X, TrendingUp, TrendingDown, Minus, Clock, MessageCircle, Send, Sparkles, Target } from 'lucide-react';
import type { UserProfile, ReputationMetrics } from '../../types';
import { getTierInfo, formatMetricLabel, formatMetricDescription, getScoreLabel, TIERS } from '../../engine/reputation';
import './ReputationLens.css';

interface Props {
  profile: UserProfile;
  isOpen: boolean;
  onClose: () => void;
}

const metricIcons: Record<keyof ReputationMetrics, typeof Clock> = {
  openingLineRate: Send,
  conversationCommitment: MessageCircle,
  responsiveness: Clock,
  thoughtfulSwipeRatio: Target,
  conversationDepth: Sparkles,
};

export default function ReputationLens({ profile, isOpen, onClose }: Props) {
  const { reputation } = profile;
  const tier = getTierInfo(reputation.tier);

  const TrendIcon = reputation.trend === 'rising' ? TrendingUp :
    reputation.trend === 'cooling' ? TrendingDown : Minus;

  const trendLabel = reputation.trend === 'rising' ? 'Trending up' :
    reputation.trend === 'cooling' ? 'Cooling off' : 'Steady';

  return (
    <AnimatePresence>
      {isOpen && (
        <>
          <motion.div
            className="lens-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />
          <motion.div
            className="lens-sheet"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', damping: 30, stiffness: 300 }}
          >
            <div className="lens-handle" />

            <button className="lens-close" onClick={onClose}>
              <X size={20} />
            </button>

            {/* Header */}
            <div className="lens-header">
              <div className="lens-header__title">
                <span className="lens-header__icon">{tier.icon}</span>
                <div>
                  <h2>{profile.firstName}'s Momentum</h2>
                  <p className="lens-header__subtitle">{tier.description}</p>
                </div>
              </div>
            </div>

            {/* Score Ring */}
            <div className="lens-score">
              <div className="lens-score__ring" style={{ '--tier-color': tier.color } as React.CSSProperties}>
                <svg viewBox="0 0 120 120" className="lens-score__svg">
                  <circle cx="60" cy="60" r="52" fill="none" stroke="rgba(0,0,0,0.06)" strokeWidth="8" />
                  <circle
                    cx="60" cy="60" r="52" fill="none"
                    stroke={tier.color}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={`${(reputation.overall / 100) * 327} 327`}
                    transform="rotate(-90 60 60)"
                    className="lens-score__progress"
                  />
                </svg>
                <div className="lens-score__value">
                  <span className="lens-score__number">{reputation.overall}</span>
                  <span className="lens-score__label">{getScoreLabel(reputation.overall)}</span>
                </div>
              </div>

              <div className="lens-score__trend">
                <TrendIcon size={14} />
                <span>{trendLabel}</span>
              </div>
            </div>

            {/* Tier Progress */}
            <div className="lens-tiers">
              <div className="lens-tiers__track">
                {TIERS.map((t, i) => (
                  <div
                    key={t.tier}
                    className={`lens-tiers__segment ${reputation.overall >= t.minScore ? 'lens-tiers__segment--filled' : ''}`}
                    style={{
                      left: `${t.minScore}%`,
                      width: `${(TIERS[i + 1]?.minScore ?? 100) - t.minScore}%`,
                      background: reputation.overall >= t.minScore ? t.color : undefined,
                    }}
                  />
                ))}
                <div
                  className="lens-tiers__marker"
                  style={{ left: `${Math.min(reputation.overall, 98)}%` }}
                />
              </div>
              <div className="lens-tiers__labels">
                {TIERS.map(t => (
                  <span key={t.tier} style={{ color: t.color }}>{t.icon}</span>
                ))}
              </div>
            </div>

            {/* Metrics */}
            <div className="lens-metrics">
              <h3 className="lens-section-title">Conversation Style</h3>
              {(Object.keys(reputation.metrics) as (keyof ReputationMetrics)[]).map(key => {
                const value = reputation.metrics[key];
                const Icon = metricIcons[key];
                return (
                  <div key={key} className="lens-metric">
                    <div className="lens-metric__icon">
                      <Icon size={16} />
                    </div>
                    <div className="lens-metric__info">
                      <div className="lens-metric__header">
                        <span className="lens-metric__name">{formatMetricLabel(key)}</span>
                        <span className="lens-metric__value">{Math.round(value * 100)}%</span>
                      </div>
                      <div className="lens-metric__bar">
                        <div
                          className="lens-metric__fill"
                          style={{
                            width: `${value * 100}%`,
                            background: value >= 0.7 ? 'var(--accent-success)' :
                              value >= 0.4 ? 'var(--accent-warm)' : 'var(--accent-secondary)',
                          }}
                        />
                      </div>
                      <span className="lens-metric__desc">{formatMetricDescription(key)}</span>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Stats */}
            <div className="lens-stats">
              <div className="lens-stat">
                <span className="lens-stat__value">{reputation.matchesTotal}</span>
                <span className="lens-stat__label">Matches</span>
              </div>
              <div className="lens-stat">
                <span className="lens-stat__value">{reputation.conversationsStarted}</span>
                <span className="lens-stat__label">Convos Started</span>
              </div>
              <div className="lens-stat">
                <span className="lens-stat__value">{reputation.avgMessagesPerConvo}</span>
                <span className="lens-stat__label">Avg Messages</span>
              </div>
              <div className="lens-stat">
                <span className="lens-stat__value">{reputation.avgResponseTimeMinutes < 60 ? `${reputation.avgResponseTimeMinutes}m` : `${Math.round(reputation.avgResponseTimeMinutes / 60)}h`}</span>
                <span className="lens-stat__label">Avg Reply</span>
              </div>
            </div>

            {/* Positive framing note */}
            <div className="lens-note">
              <Sparkles size={14} />
              <span>Momentum scores reflect conversational energy — not judgement. Everyone starts as a Spark.</span>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

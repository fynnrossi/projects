import type { ReputationMetrics, ReputationScore, ReputationTier, TierInfo } from '../types';

// ─── Tier Definitions ────────────────────────────────────────────
export const TIERS: TierInfo[] = [
  {
    tier: 'spark',
    label: 'Spark',
    color: '#FFB347',
    minScore: 0,
    icon: '✦',
    description: 'Just getting started — every conversation builds your momentum',
  },
  {
    tier: 'flame',
    label: 'Flame',
    color: '#FF6B6B',
    minScore: 40,
    icon: '🔥',
    description: 'You\'re warming up — people enjoy talking with you',
  },
  {
    tier: 'fire',
    label: 'Fire',
    color: '#C471F5',
    minScore: 65,
    icon: '💜',
    description: 'Consistent and engaging — you bring great energy',
  },
  {
    tier: 'supernova',
    label: 'Supernova',
    color: '#FFD700',
    minScore: 85,
    icon: '⭐',
    description: 'Top-tier communicator — your matches are lucky',
  },
];

// ─── Weights for composite score ─────────────────────────────────
const WEIGHTS = {
  openingLineRate: 0.25,
  conversationCommitment: 0.25,
  responsiveness: 0.20,
  thoughtfulSwipeRatio: 0.15,
  conversationDepth: 0.15,
};

// ─── Core Engine ─────────────────────────────────────────────────

export function calculateOverallScore(metrics: ReputationMetrics): number {
  const raw =
    metrics.openingLineRate * WEIGHTS.openingLineRate +
    metrics.conversationCommitment * WEIGHTS.conversationCommitment +
    metrics.responsiveness * WEIGHTS.responsiveness +
    metrics.thoughtfulSwipeRatio * WEIGHTS.thoughtfulSwipeRatio +
    metrics.conversationDepth * WEIGHTS.conversationDepth;

  return Math.round(raw * 100);
}

export function getTierForScore(score: number): ReputationTier {
  for (let i = TIERS.length - 1; i >= 0; i--) {
    if (score >= TIERS[i].minScore) return TIERS[i].tier;
  }
  return 'spark';
}

export function getTierInfo(tier: ReputationTier): TierInfo {
  return TIERS.find(t => t.tier === tier)!;
}

export function buildReputationScore(
  metrics: ReputationMetrics,
  stats: {
    matchesTotal: number;
    conversationsStarted: number;
    avgMessagesPerConvo: number;
    avgResponseTimeMinutes: number;
    memberSince: string;
  }
): ReputationScore {
  const overall = calculateOverallScore(metrics);
  const tier = getTierForScore(overall);

  return {
    overall,
    tier,
    metrics,
    trend: 'steady',
    ...stats,
  };
}

// ─── Response Time → Score Mapping ───────────────────────────────
// < 5 min = 1.0, < 30 min = 0.8, < 2 hr = 0.6, < 12 hr = 0.4, < 24 hr = 0.2, else 0.1
export function responseTimeToScore(avgMinutes: number): number {
  if (avgMinutes <= 5) return 1.0;
  if (avgMinutes <= 30) return 0.85;
  if (avgMinutes <= 120) return 0.65;
  if (avgMinutes <= 720) return 0.4;
  if (avgMinutes <= 1440) return 0.2;
  return 0.1;
}

// ─── Ghost Rate → Commitment Score ───────────────────────────────
// ghostRate 0 = 1.0 commitment, ghostRate 1 = 0.0 commitment
export function ghostRateToCommitment(ghostRate: number): number {
  return Math.max(0, Math.min(1, 1 - ghostRate));
}

// ─── Swipe Ratio Scoring ─────────────────────────────────────────
// Rewards being selective: liking 10-30% of profiles is ideal
export function swipeSelectivityScore(likeRate: number): number {
  if (likeRate <= 0.05) return 0.4;  // too picky
  if (likeRate <= 0.15) return 0.85;
  if (likeRate <= 0.30) return 1.0;  // sweet spot
  if (likeRate <= 0.50) return 0.7;
  if (likeRate <= 0.70) return 0.4;
  return 0.2; // swiping right on everyone
}

// ─── Metric Display Helpers ──────────────────────────────────────

export function formatMetricLabel(key: keyof ReputationMetrics): string {
  const labels: Record<keyof ReputationMetrics, string> = {
    openingLineRate: 'Opening Line Rate',
    conversationCommitment: 'Conversation Commitment',
    responsiveness: 'Responsiveness',
    thoughtfulSwipeRatio: 'Thoughtful Swiping',
    conversationDepth: 'Conversation Depth',
  };
  return labels[key];
}

export function formatMetricDescription(key: keyof ReputationMetrics): string {
  const descriptions: Record<keyof ReputationMetrics, string> = {
    openingLineRate: 'How often you start the conversation',
    conversationCommitment: 'How often you keep conversations going',
    responsiveness: 'How quickly you tend to reply',
    thoughtfulSwipeRatio: 'How intentionally you browse profiles',
    conversationDepth: 'How deep your conversations tend to go',
  };
  return descriptions[key];
}

export function getScoreLabel(score: number): string {
  if (score >= 85) return 'Exceptional';
  if (score >= 65) return 'Great';
  if (score >= 40) return 'Building';
  return 'Getting Started';
}

export function getMetricEmoji(value: number): string {
  if (value >= 0.8) return '🟢';
  if (value >= 0.5) return '🟡';
  return '🟠';
}

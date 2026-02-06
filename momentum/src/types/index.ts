// ─── Reputation Tiers ─────────────────────────────────────────────
export type ReputationTier = 'spark' | 'flame' | 'fire' | 'supernova';

export interface TierInfo {
  tier: ReputationTier;
  label: string;
  color: string;
  minScore: number;
  icon: string;
  description: string;
}

// ─── Reputation Metrics ───────────────────────────────────────────
export interface ReputationMetrics {
  openingLineRate: number;       // 0-1: % of matches where user sent first message
  conversationCommitment: number; // 0-1: inverse of ghost rate (1 = never ghosts)
  responsiveness: number;         // 0-1: based on avg response time
  thoughtfulSwipeRatio: number;   // 0-1: selective swiping vs spam-liking
  conversationDepth: number;      // 0-1: normalized avg messages per convo
}

export interface ReputationScore {
  overall: number;               // 0-100 composite score
  tier: ReputationTier;
  metrics: ReputationMetrics;
  trend: 'rising' | 'steady' | 'cooling'; // recent trajectory
  matchesTotal: number;
  conversationsStarted: number;
  avgMessagesPerConvo: number;
  avgResponseTimeMinutes: number;
  memberSince: string;
}

// ─── User & Profile ──────────────────────────────────────────────
export interface Prompt {
  question: string;
  answer: string;
}

export interface Photo {
  url: string;
  caption?: string;
}

export interface UserProfile {
  id: string;
  firstName: string;
  lastName: string;
  age: number;
  location: string;
  bio: string;
  occupation: string;
  company?: string;
  education?: string;
  photos: Photo[];
  prompts: Prompt[];
  interests: string[];
  height?: string;
  reputation: ReputationScore;
  verified: boolean;
}

// ─── Matching ────────────────────────────────────────────────────
export type MatchStatus = 'pending' | 'matched' | 'expired';
export type LikeType = 'like' | 'comment';

export interface Like {
  fromUserId: string;
  toUserId: string;
  type: LikeType;
  comment?: string;           // comment on a specific prompt/photo
  targetPromptIndex?: number;  // which prompt they commented on
  timestamp: string;
}

export interface Match {
  id: string;
  users: [string, string];
  status: MatchStatus;
  createdAt: string;
  like: Like;
  lastActivity?: string;
  hasUnread: boolean;
}

// ─── Conversations ───────────────────────────────────────────────
export interface Message {
  id: string;
  senderId: string;
  content: string;
  timestamp: string;
  read: boolean;
  type: 'text' | 'opener' | 'gif' | 'prompt-reply';
}

export interface Conversation {
  id: string;
  matchId: string;
  participants: [string, string];
  messages: Message[];
  startedAt: string;
  lastMessageAt: string;
  isActive: boolean;
}

// ─── App State ───────────────────────────────────────────────────
export interface AppState {
  currentUser: UserProfile;
  discoverQueue: UserProfile[];
  matches: Match[];
  conversations: Conversation[];
  likesSent: Like[];
  likesReceived: Like[];
}

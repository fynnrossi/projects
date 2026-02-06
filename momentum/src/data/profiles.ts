import type { UserProfile } from '../types';
import { buildReputationScore, ghostRateToCommitment, responseTimeToScore, swipeSelectivityScore } from '../engine/reputation';

// Gradient placeholder images using UI avatars / DiceBear style
const photo = (seed: string, idx: number): string =>
  `https://api.dicebear.com/7.x/lorelei/svg?seed=${seed}${idx}&backgroundColor=b6e3f4,c0aede,d1d4f9,ffd5dc,ffdfbf`;

const buildProfile = (
  id: string,
  firstName: string,
  lastName: string,
  age: number,
  location: string,
  bio: string,
  occupation: string,
  prompts: { question: string; answer: string }[],
  interests: string[],
  repConfig: {
    openingLineRate: number;
    ghostRate: number;
    avgResponseMin: number;
    likeRate: number;
    avgMsgPerConvo: number;
    matchesTotal: number;
    conversationsStarted: number;
    memberSince: string;
  },
  extra?: Partial<UserProfile>
): UserProfile => {
  const metrics = {
    openingLineRate: repConfig.openingLineRate,
    conversationCommitment: ghostRateToCommitment(repConfig.ghostRate),
    responsiveness: responseTimeToScore(repConfig.avgResponseMin),
    thoughtfulSwipeRatio: swipeSelectivityScore(repConfig.likeRate),
    conversationDepth: Math.min(1, repConfig.avgMsgPerConvo / 40),
  };

  return {
    id,
    firstName,
    lastName,
    age,
    location,
    bio,
    occupation,
    photos: [
      { url: photo(firstName, 1) },
      { url: photo(firstName, 2) },
      { url: photo(firstName, 3) },
    ],
    prompts,
    interests,
    reputation: buildReputationScore(metrics, {
      matchesTotal: repConfig.matchesTotal,
      conversationsStarted: repConfig.conversationsStarted,
      avgMessagesPerConvo: repConfig.avgMsgPerConvo,
      avgResponseTimeMinutes: repConfig.avgResponseMin,
      memberSince: repConfig.memberSince,
    }),
    verified: true,
    ...extra,
  };
};

// ─── Current User (You) ──────────────────────────────────────────
export const currentUser: UserProfile = buildProfile(
  'user-me',
  'Alex',
  'Morgan',
  28,
  'London, UK',
  'Product designer by day, terrible cook by night. Looking for someone who appreciates a good sunset and bad puns.',
  'Product Designer',
  [
    { question: 'A life goal of mine', answer: 'To visit every national park in Europe before 35. Currently at 12/47.' },
    { question: 'The way to win me over is', answer: 'Send me a voice note instead of a text. There\'s something about hearing someone laugh.' },
    { question: 'My most controversial opinion', answer: 'Cereal is a soup. I will not be taking questions.' },
  ],
  ['Design', 'Hiking', 'Photography', 'Cooking', 'Travel', 'Music'],
  {
    openingLineRate: 0.75,
    ghostRate: 0.08,
    avgResponseMin: 18,
    likeRate: 0.22,
    avgMsgPerConvo: 28,
    matchesTotal: 34,
    conversationsStarted: 26,
    memberSince: '2025-09-15',
  },
  { company: 'Figma', education: 'UAL London', height: '5\'11"' }
);

// ─── Discover Queue Profiles ─────────────────────────────────────
export const discoverProfiles: UserProfile[] = [
  buildProfile(
    'user-1',
    'Maya',
    'Chen',
    26,
    'East London',
    'Architect who builds things in real life and in Minecraft. Yes, both are equally important.',
    'Architect',
    [
      { question: 'I\'m convinced that', answer: 'The best conversations happen after midnight, walking home from somewhere.' },
      { question: 'Together, we could', answer: 'Design our dream tiny house, then argue about whether it needs a reading nook or a vinyl corner.' },
      { question: 'A shower thought I had recently', answer: 'Buildings are just fancy caves we decorated.' },
    ],
    ['Architecture', 'Gaming', 'Vinyl Records', 'Sketching', 'Rock Climbing'],
    {
      openingLineRate: 0.82,
      ghostRate: 0.05,
      avgResponseMin: 12,
      likeRate: 0.18,
      avgMsgPerConvo: 35,
      matchesTotal: 41,
      conversationsStarted: 34,
      memberSince: '2025-08-01',
    },
    { education: 'Bartlett School of Architecture', height: '5\'6"' }
  ),

  buildProfile(
    'user-2',
    'James',
    'Okafor',
    30,
    'Shoreditch',
    'Chef who can\'t stop talking about fermentation. I\'m fun at parties, I promise.',
    'Head Chef',
    [
      { question: 'The way to win me over is', answer: 'Ask me what I\'m fermenting right now. I dare you.' },
      { question: 'My simple pleasures', answer: 'The sound of sourdough crust cracking. Saturday morning markets. A perfectly timed joke.' },
      { question: 'I go crazy for', answer: 'Anyone who eats with their hands and isn\'t afraid to make a mess.' },
    ],
    ['Cooking', 'Fermentation', 'Jazz', 'Markets', 'Cycling', 'Wine'],
    {
      openingLineRate: 0.90,
      ghostRate: 0.03,
      avgResponseMin: 8,
      likeRate: 0.15,
      avgMsgPerConvo: 42,
      matchesTotal: 55,
      conversationsStarted: 50,
      memberSince: '2025-06-20',
    },
    { company: 'Ottolenghi', height: '6\'1"' }
  ),

  buildProfile(
    'user-3',
    'Priya',
    'Sharma',
    27,
    'Camden Town',
    'Documentary filmmaker chasing stories. Currently obsessed with urban beekeeping.',
    'Documentary Filmmaker',
    [
      { question: 'I\'m looking for', answer: 'Someone who has opinions about things. Strong ones. Even if they\'re about sandwich fillings.' },
      { question: 'The hallmark of a good relationship is', answer: 'Being able to sit in comfortable silence and not reach for your phone.' },
      { question: 'My greatest strength', answer: 'I remember the small things people tell me. Your favourite ice cream flavour is safe with me.' },
    ],
    ['Film', 'Bees', 'Street Food', 'Podcasts', 'Yoga', 'Writing'],
    {
      openingLineRate: 0.65,
      ghostRate: 0.12,
      avgResponseMin: 45,
      likeRate: 0.25,
      avgMsgPerConvo: 22,
      matchesTotal: 28,
      conversationsStarted: 18,
      memberSince: '2025-10-05',
    },
    { education: 'London Film School', height: '5\'4"' }
  ),

  buildProfile(
    'user-4',
    'Tom',
    'Brennan',
    29,
    'Hackney',
    'Physiotherapist and marathon runner. I can fix your back and outrun your emotional baggage.',
    'Physiotherapist',
    [
      { question: 'A life goal of mine', answer: 'Run a marathon on every continent. Done 4, Antarctica is going to be interesting.' },
      { question: 'I\'ll know it\'s time to delete this app when', answer: 'Someone makes me laugh so hard I snort in public. That\'s the bar.' },
      { question: 'Typical Sunday', answer: 'Long run, farmers market, aggressive napping, then pretending I\'m going to cook but ordering Thai.' },
    ],
    ['Running', 'Health', 'Thai Food', 'Comedy', 'Dogs', 'Travel'],
    {
      openingLineRate: 0.55,
      ghostRate: 0.20,
      avgResponseMin: 90,
      likeRate: 0.40,
      avgMsgPerConvo: 15,
      matchesTotal: 38,
      conversationsStarted: 21,
      memberSince: '2025-11-12',
    },
    { company: 'NHS', height: '6\'0"' }
  ),

  buildProfile(
    'user-5',
    'Sofia',
    'Rossi',
    25,
    'Notting Hill',
    'Art curator by day, DJ by every other Friday. My spotify wrapped is a personality test.',
    'Art Curator',
    [
      { question: 'My most controversial opinion', answer: 'Museums should have beds. Some of that art deserves to be stared at for hours.' },
      { question: 'Together, we could', answer: 'Spend an afternoon in a gallery making up backstories for every person in every painting.' },
      { question: 'I\'m convinced that', answer: 'The right song at the right moment can genuinely change your life.' },
    ],
    ['Art', 'Music', 'DJing', 'Gallery Hopping', 'Fashion', 'Dance'],
    {
      openingLineRate: 0.78,
      ghostRate: 0.06,
      avgResponseMin: 15,
      likeRate: 0.20,
      avgMsgPerConvo: 32,
      matchesTotal: 47,
      conversationsStarted: 37,
      memberSince: '2025-07-30',
    },
    { education: 'Goldsmiths', height: '5\'7"' }
  ),

  buildProfile(
    'user-6',
    'Kai',
    'Nakamura',
    31,
    'Bermondsey',
    'Software engineer who writes poetry in commit messages. Looking for someone to debug my love life.',
    'Software Engineer',
    [
      { question: 'A shower thought I had recently', answer: 'If you think about it, dating apps are just distributed systems with really bad error handling.' },
      { question: 'The way to win me over is', answer: 'Tell me about something you\'re obsessed with. I don\'t care what it is. Passion is attractive.' },
      { question: 'My simple pleasures', answer: 'Clean code, a flat white, and when the tube arrives the second you walk onto the platform.' },
    ],
    ['Coding', 'Poetry', 'Coffee', 'Board Games', 'Sci-Fi', 'Ramen'],
    {
      openingLineRate: 0.88,
      ghostRate: 0.04,
      avgResponseMin: 10,
      likeRate: 0.12,
      avgMsgPerConvo: 38,
      matchesTotal: 32,
      conversationsStarted: 28,
      memberSince: '2025-08-15',
    },
    { company: 'Monzo', education: 'Imperial College', height: '5\'9"' }
  ),

  buildProfile(
    'user-7',
    'Ella',
    'Wright',
    28,
    'Peckham',
    'Primary school teacher who accidentally became a TikTok pottery influencer. Life is weird.',
    'Teacher & Potter',
    [
      { question: 'I go crazy for', answer: 'A good bookshop. If you take me to a secondhand bookshop on a first date, I\'m already half in love.' },
      { question: 'I\'ll know it\'s time to delete this app when', answer: 'I find someone who\'ll watch terrible reality TV with me without judgement.' },
      { question: 'My greatest strength', answer: 'I can make anyone feel comfortable. Kids, adults, your scary mum. I\'ve got it covered.' },
    ],
    ['Pottery', 'Reading', 'Teaching', 'Reality TV', 'Plants', 'Baking'],
    {
      openingLineRate: 0.70,
      ghostRate: 0.10,
      avgResponseMin: 25,
      likeRate: 0.28,
      avgMsgPerConvo: 26,
      matchesTotal: 36,
      conversationsStarted: 25,
      memberSince: '2025-09-01',
    },
    { education: 'UCL', height: '5\'5"' }
  ),

  buildProfile(
    'user-8',
    'Marcus',
    'Adebayo',
    32,
    'Brixton',
    'Music producer and vinyl obsessive. My flat is 40% records, 40% plants, 20% liveable space.',
    'Music Producer',
    [
      { question: 'A life goal of mine', answer: 'Score a film soundtrack. Something moody and beautiful that makes people cry in cinemas.' },
      { question: 'The hallmark of a good relationship is', answer: 'Being each other\'s hype person. I want someone who\'ll gas me up and let me gas them up too.' },
      { question: 'Together, we could', answer: 'Make a playlist for every mood. Road trip? Done. Cooking dinner? Done. Existential crisis at 2am? Covered.' },
    ],
    ['Music Production', 'Vinyl', 'Plants', 'Film', 'Basketball', 'Afrobeats'],
    {
      openingLineRate: 0.85,
      ghostRate: 0.02,
      avgResponseMin: 6,
      likeRate: 0.10,
      avgMsgPerConvo: 45,
      matchesTotal: 29,
      conversationsStarted: 25,
      memberSince: '2025-07-01',
    },
    { height: '6\'2"' }
  ),
];

// ─── Mock Matches ────────────────────────────────────────────────
export const mockMatches = [
  {
    id: 'match-1',
    users: ['user-me', 'user-1'] as [string, string],
    status: 'matched' as const,
    createdAt: '2026-01-28T14:00:00Z',
    like: {
      fromUserId: 'user-me',
      toUserId: 'user-1',
      type: 'comment' as const,
      comment: 'A vinyl corner AND a reading nook — you just need a bigger tiny house 😄',
      targetPromptIndex: 1,
      timestamp: '2026-01-28T14:00:00Z',
    },
    lastActivity: '2026-02-05T18:30:00Z',
    hasUnread: true,
  },
  {
    id: 'match-2',
    users: ['user-me', 'user-5'] as [string, string],
    status: 'matched' as const,
    createdAt: '2026-01-25T10:00:00Z',
    like: {
      fromUserId: 'user-5',
      toUserId: 'user-me',
      type: 'comment' as const,
      comment: 'Cereal is a soup?! I need to hear the full legal argument for this.',
      targetPromptIndex: 2,
      timestamp: '2026-01-25T10:00:00Z',
    },
    lastActivity: '2026-02-04T22:15:00Z',
    hasUnread: false,
  },
  {
    id: 'match-3',
    users: ['user-me', 'user-6'] as [string, string],
    status: 'matched' as const,
    createdAt: '2026-02-01T09:00:00Z',
    like: {
      fromUserId: 'user-6',
      toUserId: 'user-me',
      type: 'comment' as const,
      comment: 'A product designer at Figma? We should argue about design systems sometime.',
      targetPromptIndex: 0,
      timestamp: '2026-02-01T09:00:00Z',
    },
    lastActivity: '2026-02-05T20:00:00Z',
    hasUnread: true,
  },
  {
    id: 'match-4',
    users: ['user-me', 'user-7'] as [string, string],
    status: 'matched' as const,
    createdAt: '2026-02-03T16:00:00Z',
    like: {
      fromUserId: 'user-me',
      toUserId: 'user-7',
      type: 'like' as const,
      timestamp: '2026-02-03T16:00:00Z',
    },
    lastActivity: '2026-02-03T16:00:00Z',
    hasUnread: false,
  },
];

// ─── Mock Conversations ──────────────────────────────────────────
export const mockConversations = [
  {
    id: 'convo-1',
    matchId: 'match-1',
    participants: ['user-me', 'user-1'] as [string, string],
    startedAt: '2026-01-28T14:30:00Z',
    lastMessageAt: '2026-02-05T18:30:00Z',
    isActive: true,
    messages: [
      { id: 'm1', senderId: 'user-me', content: 'A vinyl corner AND a reading nook — you just need a bigger tiny house 😄', timestamp: '2026-01-28T14:30:00Z', read: true, type: 'opener' as const },
      { id: 'm2', senderId: 'user-1', content: 'Haha okay but hear me out — what if the reading nook IS the vinyl corner? Multifunctional design is literally my job 😌', timestamp: '2026-01-28T15:02:00Z', read: true, type: 'text' as const },
      { id: 'm3', senderId: 'user-me', content: 'A reading nook with a turntable... that\'s dangerously close to my ideal Saturday', timestamp: '2026-01-28T15:15:00Z', read: true, type: 'text' as const },
      { id: 'm4', senderId: 'user-1', content: 'What are you spinning these days? I just got a first press of In Rainbows and I won\'t shut up about it', timestamp: '2026-01-28T15:45:00Z', read: true, type: 'text' as const },
      { id: 'm5', senderId: 'user-me', content: 'In Rainbows! Okay we might need to have that tiny house argument sooner than expected. I\'ve been on a Khruangbin kick lately', timestamp: '2026-01-28T16:00:00Z', read: true, type: 'text' as const },
      { id: 'm6', senderId: 'user-1', content: 'Khruangbin is perfect background music for sketching. Do you ever draw or is it all digital design for you?', timestamp: '2026-01-29T09:12:00Z', read: true, type: 'text' as const },
      { id: 'm7', senderId: 'user-me', content: 'Mostly digital but I keep a sketchbook for bad ideas. Some real gems in there — I drew a "couch that\'s also a bath" last week', timestamp: '2026-01-29T09:30:00Z', read: true, type: 'text' as const },
      { id: 'm8', senderId: 'user-1', content: 'I need to see this immediately. As an architect I have professional concerns AND personal excitement about this concept', timestamp: '2026-01-29T09:35:00Z', read: true, type: 'text' as const },
      { id: 'm9', senderId: 'user-1', content: 'Also we should grab a coffee sometime? There\'s a great spot near the Barbican that does vinyl listening sessions on weekends', timestamp: '2026-02-05T18:30:00Z', read: false, type: 'text' as const },
    ],
  },
  {
    id: 'convo-2',
    matchId: 'match-2',
    participants: ['user-me', 'user-5'] as [string, string],
    startedAt: '2026-01-25T10:30:00Z',
    lastMessageAt: '2026-02-04T22:15:00Z',
    isActive: true,
    messages: [
      { id: 'm10', senderId: 'user-5', content: 'Cereal is a soup?! I need to hear the full legal argument for this.', timestamp: '2026-01-25T10:30:00Z', read: true, type: 'opener' as const },
      { id: 'm11', senderId: 'user-me', content: 'Exhibit A: liquid base. Exhibit B: solid ingredients suspended in said liquid. Exhibit C: served in a bowl. The defence rests.', timestamp: '2026-01-25T11:00:00Z', read: true, type: 'text' as const },
      { id: 'm12', senderId: 'user-5', content: 'Objection! Soup is cooked. You can\'t just pour cold milk on cheerios and call it cuisine', timestamp: '2026-01-25T11:15:00Z', read: true, type: 'text' as const },
      { id: 'm13', senderId: 'user-me', content: 'Gazpacho would like a word 🍅', timestamp: '2026-01-25T11:18:00Z', read: true, type: 'text' as const },
      { id: 'm14', senderId: 'user-5', content: '...okay that\'s actually a really good point. I\'m shaken. What other chaos theories do you have?', timestamp: '2026-01-25T11:25:00Z', read: true, type: 'text' as const },
      { id: 'm15', senderId: 'user-me', content: 'A hotdog is a taco. But I\'ll save that one for date two 😄', timestamp: '2026-02-04T22:15:00Z', read: true, type: 'text' as const },
    ],
  },
  {
    id: 'convo-3',
    matchId: 'match-3',
    participants: ['user-me', 'user-6'] as [string, string],
    startedAt: '2026-02-01T09:30:00Z',
    lastMessageAt: '2026-02-05T20:00:00Z',
    isActive: true,
    messages: [
      { id: 'm16', senderId: 'user-6', content: 'A product designer at Figma? We should argue about design systems sometime.', timestamp: '2026-02-01T09:30:00Z', read: true, type: 'opener' as const },
      { id: 'm17', senderId: 'user-me', content: 'Only if you promise to write the commit message as a haiku', timestamp: '2026-02-01T10:00:00Z', read: true, type: 'text' as const },
      { id: 'm18', senderId: 'user-6', content: 'Buttons need more space / The padding is never right / Ship it anyway', timestamp: '2026-02-01T10:05:00Z', read: true, type: 'text' as const },
      { id: 'm19', senderId: 'user-me', content: 'That is genuinely beautiful. I\'m putting that on a poster for my team', timestamp: '2026-02-01T10:12:00Z', read: true, type: 'text' as const },
      { id: 'm20', senderId: 'user-6', content: 'I have more where that came from. My git log reads like a poetry anthology. "Refactored with tenderness" is a recent favourite', timestamp: '2026-02-05T20:00:00Z', read: false, type: 'text' as const },
    ],
  },
];

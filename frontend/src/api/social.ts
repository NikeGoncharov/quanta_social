// Typed client for auth + the social network. Mirrors api/cabinet.ts: thin wrappers over the
// shared `req` helper (relative /api, cookie-based JWT). The sponsored feed item reuses the
// cabinet's Creative type so one CreativePreview renders both the cabinet and the feed.
import type { Creative } from "./cabinet";
import { req } from "./client";

export interface Me {
  id: string;
  email: string | null;
  handle: string;
  display_name: string;
  avatar_seed: string;
  bio: string;
  interests: string[];
  geo: string;
  age_band: string;
  gender: string;
  is_synthetic: boolean;
}

export interface UserBrief {
  id: string;
  handle: string;
  display_name: string;
  avatar_seed: string;
  is_synthetic: boolean;
}

export interface ProfilePublic extends UserBrief {
  bio: string;
  interests: string[];
  geo: string;
  age_band: string;
  gender: string;
  followers: number;
  following: number;
  posts: number;
  is_following: boolean;
  is_me: boolean;
}

export interface PostItem {
  id: string;
  author: UserBrief;
  body: string;
  image_key: string | null;
  created_at: number;
  like_count: number;
  comment_count: number;
  liked: boolean;
}

export interface CommentItem {
  id: string;
  author: UserBrief;
  body: string;
  created_at: number;
}

export interface PostDetail extends PostItem {
  comments: CommentItem[];
}

export interface FeedPost {
  kind: "post";
  post: PostItem;
}

export interface FeedAd {
  kind: "ad";
  impression_id: string;
  ad_id: string;
  campaign_id: string;
  brand: string;
  clearing: number;
  creative: Creative;
}

export type FeedItem = FeedPost | FeedAd;

export interface Conversation {
  peer: UserBrief;
  last: string | null;
  last_at: number;
  last_from_me: boolean;
  unread: number;
}

export interface ThreadMessage {
  id: string;
  from_me: boolean;
  body: string;
  created_at: number;
}

export interface Thread {
  peer: UserBrief;
  messages: ThreadMessage[];
}

export interface ClickResult {
  clicked: boolean;
  converted: boolean;
  value_usd: number;
  repeat?: boolean;
}

export interface ProfilePatch {
  display_name?: string;
  bio?: string;
  interests?: string[];
  geo?: string;
  age_band?: string;
  gender?: string;
  avatar_seed?: string;
}

const j = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });

export const socialApi = {
  // auth
  me: () => req<Me>("/auth/me"),
  register: (email: string, password: string, handle?: string) =>
    req<{ id: string; handle: string }>("/auth/register", j({ email, password, handle })),
  login: (email: string, password: string) =>
    req<{ access_token: string }>("/auth/login", j({ email, password })),
  logout: () => req<{ status: string }>("/auth/logout", { method: "POST" }),

  // feed
  feed: (limit = 24) => req<{ items: FeedItem[] }>(`/social/feed?limit=${limit}`),
  clickSponsored: (impressionId: string) =>
    req<ClickResult>(`/social/sponsored/${impressionId}/click`, { method: "POST" }),

  // profiles + graph
  profile: (handle: string) => req<ProfilePublic>(`/social/users/${handle}`),
  userPosts: (handle: string) => req<{ posts: PostItem[] }>(`/social/users/${handle}/posts`),
  updateProfile: (body: ProfilePatch) =>
    req<ProfilePublic>("/social/profile", { method: "PATCH", body: JSON.stringify(body) }),
  follow: (handle: string) => req<{ following: boolean }>(`/social/users/${handle}/follow`, { method: "POST" }),
  unfollow: (handle: string) => req<{ following: boolean }>(`/social/users/${handle}/follow`, { method: "DELETE" }),
  suggestions: () => req<{ users: UserBrief[] }>("/social/suggestions"),

  // posts
  createPost: (body: string, image_key?: string | null) =>
    req<PostItem>("/social/posts", j({ body, image_key })),
  post: (id: string) => req<PostDetail>(`/social/posts/${id}`),
  deletePost: (id: string) => req<{ deleted: boolean }>(`/social/posts/${id}`, { method: "DELETE" }),
  like: (id: string) => req<{ liked: boolean; like_count: number }>(`/social/posts/${id}/like`, { method: "POST" }),
  unlike: (id: string) => req<{ liked: boolean; like_count: number }>(`/social/posts/${id}/like`, { method: "DELETE" }),
  comment: (id: string, body: string) => req<CommentItem>(`/social/posts/${id}/comments`, j({ body })),

  // messages
  conversations: () => req<{ conversations: Conversation[] }>("/social/messages"),
  thread: (handle: string) => req<Thread>(`/social/messages/${handle}`),
  sendMessage: (handle: string, body: string) => req<ThreadMessage>(`/social/messages/${handle}`, j({ body })),
};

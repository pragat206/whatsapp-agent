export type Role = "admin" | "campaign_manager" | "support_agent" | "viewer";

export interface Me {
  id: string;
  email: string;
  name: string;
  role: Role;
}

export type ConversationState =
  | "AI_ACTIVE"
  | "AI_PAUSED"
  | "HUMAN_ACTIVE"
  | "CLOSED";

export interface Contact {
  id: string;
  phone_e164: string;
  name?: string | null;
  city?: string | null;
  state?: string | null;
  tags: string[];
  unsubscribed: boolean;
}

export interface ConversationSummary {
  id: string;
  state: ConversationState;
  contact: Contact;
  last_inbound_at?: string | null;
  last_outbound_at?: string | null;
  last_message_preview?: string | null;
  unread_count: number;
  source_campaign_id?: string | null;
  assigned_user_id?: string | null;
  tags: string[];
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  direction: "inbound" | "outbound";
  sender_kind: string;
  body: string;
  status: string;
  template_name?: string | null;
  created_at: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Campaign {
  id: string;
  name: string;
  objective?: string | null;
  status: string;
  template_name: string;
  template_params_schema: string[];
  tags: string[];
  scheduled_at?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface CampaignMetrics {
  total: number;
  valid: number;
  invalid: number;
  sent: number;
  delivered: number;
  read: number;
  replied: number;
  failed: number;
  pending: number;
}

import type { ConversationState } from "@/lib/types";

const LABEL: Record<ConversationState, string> = {
  AI_ACTIVE: "AI",
  AI_PAUSED: "Paused",
  HUMAN_ACTIVE: "Human",
  CLOSED: "Closed"
};

const CLS: Record<ConversationState, string> = {
  AI_ACTIVE: "ai",
  AI_PAUSED: "paused",
  HUMAN_ACTIVE: "human",
  CLOSED: "closed"
};

export default function StatePill({ state }: { state: ConversationState }) {
  return <span className={`pill ${CLS[state]}`}>{LABEL[state]}</span>;
}

import type { QueueCard } from "./types";

export type Phase = "prompt" | "answer" | "grading" | "done";

export interface ReviewState {
  cards: QueueCard[];
  index: number;
  phase: Phase;
  graded: number;
  totalDue: number;
  lastNextReviewAt: string | null;
  error: string | null;
}

export function load(cards: QueueCard[], totalDue: number): ReviewState {
  return {
    cards,
    index: 0,
    phase: cards.length === 0 ? "done" : "prompt",
    graded: 0,
    totalDue,
    lastNextReviewAt: null,
    error: null,
  };
}

export function current(state: ReviewState): QueueCard | null {
  return state.phase === "done" ? null : (state.cards[state.index] ?? null);
}

export function reveal(state: ReviewState): ReviewState {
  if (state.phase !== "prompt") return state;
  return { ...state, phase: "answer" };
}

export function startGrading(state: ReviewState): ReviewState {
  if (state.phase !== "answer") return state;
  return { ...state, phase: "grading", error: null };
}

export function gradeSucceeded(state: ReviewState, nextReviewAt: string): ReviewState {
  return advance({ ...state, graded: state.graded + 1, lastNextReviewAt: nextReviewAt });
}

export function gradeFailed(state: ReviewState, message: string): ReviewState {
  return { ...state, phase: "answer", error: message };
}

// Used when the server says the card no longer exists (deleted meanwhile): drop it silently.
export function skipCurrent(state: ReviewState): ReviewState {
  return advance(state);
}

export function remaining(state: ReviewState): number {
  return state.phase === "done" ? 0 : state.cards.length - state.index;
}

export function progress(state: ReviewState): { done: number; total: number } {
  return { done: state.graded, total: Math.max(state.totalDue, state.cards.length) };
}

export function hasMoreOnServer(state: ReviewState): boolean {
  return state.totalDue > state.cards.length;
}

function advance(state: ReviewState): ReviewState {
  const nextIndex = state.index + 1;
  if (nextIndex >= state.cards.length) {
    return { ...state, index: nextIndex, phase: "done", error: null };
  }
  return { ...state, index: nextIndex, phase: "prompt", error: null };
}

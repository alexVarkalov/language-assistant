import { describe, expect, it } from "vitest";

import * as rs from "./reviewState";
import type { QueueCard } from "./types";

function card(id: number): QueueCard {
  return {
    id,
    direction: "target",
    prompt_text: `p${id}`,
    prompt_lang: "PL",
    answer_text: `a${id}`,
    answer_lang: "RU",
    repetition: 0,
    interval_days: 0,
    next_review_at: "2026-09-13T08:00:00Z",
  };
}

describe("reviewState", () => {
  it("starts in prompt phase with the first card", () => {
    const state = rs.load([card(1), card(2)], 5);
    expect(state.phase).toBe("prompt");
    expect(rs.current(state)?.id).toBe(1);
    expect(rs.progress(state)).toEqual({ done: 0, total: 5 });
    expect(rs.hasMoreOnServer(state)).toBe(true);
  });

  it("is done immediately when the queue is empty", () => {
    const state = rs.load([], 0);
    expect(state.phase).toBe("done");
    expect(rs.current(state)).toBeNull();
  });

  it("reveal only works from prompt", () => {
    const state = rs.load([card(1)], 1);
    const revealed = rs.reveal(state);
    expect(revealed.phase).toBe("answer");
    expect(rs.reveal(revealed)).toBe(revealed);
  });

  it("grading advances and finishes on the last card", () => {
    let state = rs.load([card(1), card(2)], 2);
    state = rs.startGrading(rs.reveal(state));
    expect(state.phase).toBe("grading");
    state = rs.gradeSucceeded(state, "2026-09-20T08:00:00Z");
    expect(state.phase).toBe("prompt");
    expect(rs.current(state)?.id).toBe(2);
    expect(state.graded).toBe(1);

    state = rs.gradeSucceeded(rs.startGrading(rs.reveal(state)), "2026-09-21T08:00:00Z");
    expect(state.phase).toBe("done");
    expect(state.graded).toBe(2);
    expect(state.lastNextReviewAt).toBe("2026-09-21T08:00:00Z");
    expect(rs.remaining(state)).toBe(0);
  });

  it("a failed grade returns to the answer side with an error", () => {
    let state = rs.startGrading(rs.reveal(rs.load([card(1)], 1)));
    state = rs.gradeFailed(state, "boom");
    expect(state.phase).toBe("answer");
    expect(state.error).toBe("boom");
    expect(state.graded).toBe(0);
  });

  it("skipping a vanished card does not count as graded", () => {
    let state = rs.startGrading(rs.reveal(rs.load([card(1), card(2)], 2)));
    state = rs.skipCurrent(state);
    expect(rs.current(state)?.id).toBe(2);
    expect(state.graded).toBe(0);
  });

  it("startGrading is a no-op outside the answer phase", () => {
    const state = rs.load([card(1)], 1);
    expect(rs.startGrading(state)).toBe(state);
  });
});

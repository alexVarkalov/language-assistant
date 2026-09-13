export type Locale = "en" | "ru";
export type Direction = "source" | "target";
export type Quality = 0 | 3 | 5;

export interface LangPair {
  source: string;
  target: string;
}

export interface Me {
  telegram_id: number;
  locale: Locale;
  timezone: string;
  lang_pair: LangPair;
  due_count: number;
  short_review_interval_minutes: number;
}

export interface QueueCard {
  id: number;
  direction: Direction;
  prompt_text: string;
  prompt_lang: string;
  answer_text: string;
  answer_lang: string;
  repetition: number;
  interval_days: number;
  next_review_at: string;
}

export interface QueueResponse {
  cards: QueueCard[];
  total_due: number;
}

export interface GradeResponse {
  card_id: number;
  next_review_at: string;
  interval_days: number;
  ease_factor: number;
  repetition: number;
}

export interface ErrorBody {
  error: string;
  message: string;
}

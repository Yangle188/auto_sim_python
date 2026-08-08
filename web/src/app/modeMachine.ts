import type { StatusPayload } from "../types";

export type UiMode = "author" | "drive" | "review";

/** 根据会话状态推导默认模式；用户显式选择优先 */
export function deriveMode(
  status: StatusPayload,
  userMode: UiMode | null,
  editing: boolean
): UiMode {
  if (userMode) return userMode;
  if (editing) return "author";
  if (status.scrubbing) return "review";
  if (status.status === "idle" || status.status === "finished") return "author";
  return "drive";
}

export const MODE_LABEL: Record<UiMode, string> = {
  author: "Author",
  drive: "Drive",
  review: "Review",
};

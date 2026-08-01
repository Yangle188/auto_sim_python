/** 界面中文文案 */

export const STATUS_ZH: Record<string, string> = {
  idle: "空闲",
  running: "运行中",
  paused: "已暂停",
  finished: "已结束",
};

export const AD_STATE_ZH: Record<string, string> = {
  OFF: "关机",
  PASSIVE: "被动",
  STANDBY: "待机",
  ACTIVE: "激活",
  OVERRIDE: "接管",
};

export const ROAD_CLASS_ZH: Record<string, string> = {
  main: "主路",
  aux: "辅路",
};

export const MANEUVER_ZH: Record<string, string> = {
  straight: "直行",
  left: "左转",
  right: "右转",
  merge: "汇入",
  diverge: "分流",
};

export function statusZh(s: string): string {
  return STATUS_ZH[s] || s;
}

export function adStateZh(s: string): string {
  return AD_STATE_ZH[s] || s;
}

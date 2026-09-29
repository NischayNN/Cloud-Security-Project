export const SEVERITIES = ["Critical", "High", "Medium", "Low"];
export const STATUSES = ["Detected", "Investigating", "Contained", "Resolved"];
export const sevColor = (s) => `var(--${s})`;
export const fmt = (t) => new Date(t).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

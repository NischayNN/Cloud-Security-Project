export const SEVERITIES = ["Critical", "High", "Medium", "Low"];
export const STATUSES = ["Detected", "Investigating", "Contained", "Resolved"];
export const sevColor = (s) => `var(--${s})`;
export const fmt = (t) => new Date(t).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });

export const originLabel = (origin) => ({
  demo: "Demo sample",
  "aws-cloudtrail": "AWS CloudTrail",
  fixture: "Test fixture",
  submitted: "Submitted / unverified",
}[origin] || "Submitted / unverified");

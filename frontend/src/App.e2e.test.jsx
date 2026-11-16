// End-to-end check: React <App /> against mocked backend API responses.
// Tests filtering, status progression, search, and empty/error states without demo dependencies.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App.jsx";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const items = () => screen.queryAllByTestId("incident-item");
const click = (el) => fireEvent.click(el);
const button = (name) => screen.getByRole("button", { name });
const tileCount = (s) => String(Number(within(screen.getByTestId(`tile-${s}`)).getByText(/^\d+$/).textContent));

const MOCK_INCIDENTS = [
  {
    incident_id: "INC-TEST01",
    type: "open_ssh_security_group",
    title: "SSH open to the world: sg-prod",
    description: "Security group ingress rule open to 0.0.0.0/0",
    severity: "Critical",
    severity_score: 85,
    severity_reasons: ["SSH reachable from the entire internet (+60)", "Production security group (+20)"],
    status: "Detected",
    provider: "aws",
    resource_type: "security_group",
    resource_id: "sg-prod",
    actor: "arn:aws:iam::123456789012:user/admin",
    event: {
      event_id: "evt-test-01",
      origin: "aws-cloudtrail",
      provider: "aws",
      source: "ec2.amazonaws.com",
      event_name: "AuthorizeSecurityGroupIngress",
      event_time: "2026-10-07T12:00:00Z",
      region: "ap-south-1",
      account_id: "123456789012",
      actor: "admin",
      source_ip: "198.51.100.1",
      resource_type: "security_group",
      resource_id: "sg-prod",
      details: { rules: [{ protocol: "tcp", from_port: 22, to_port: 22, cidr: "0.0.0.0/0" }] },
    },
    playbook: [
      { title: "Confirm the rule", action: "Inspect the security group.", command: "aws ec2 describe-security-groups --group-ids <SG_ID>", done: false },
      { title: "Remove the open rule", action: "Revoke the ingress rule.", command: "aws ec2 revoke-security-group-ingress", done: false },
    ],
    history: [{ status: "Detected", timestamp: "2026-10-07T12:00:00Z", note: "Incident automatically detected" }],
    created_at: "2026-10-07T12:00:00Z",
    updated_at: "2026-10-07T12:00:00Z",
  },
  {
    incident_id: "INC-TEST02",
    type: "public_s3_bucket",
    title: "Public S3 bucket: data-archive",
    description: "S3 bucket has public read ACL",
    severity: "Medium",
    severity_score: 50,
    severity_reasons: ["Bucket is publicly accessible (+50)"],
    status: "Detected",
    provider: "aws",
    resource_type: "s3_bucket",
    resource_id: "data-archive",
    actor: "arn:aws:iam::123456789012:user/developer",
    event: {
      event_id: "evt-test-02",
      origin: "submitted",
      provider: "aws",
      source: "s3.amazonaws.com",
      event_name: "PutBucketAcl",
      event_time: "2026-10-07T12:05:00Z",
      region: "ap-south-1",
      account_id: "123456789012",
      actor: "developer",
      source_ip: "198.51.100.2",
      resource_type: "s3_bucket",
      resource_id: "data-archive",
      details: { public_permissions: ["READ"] },
    },
    playbook: [
      { title: "Confirm exposure", action: "Check bucket ACL.", command: "aws s3api get-bucket-acl", done: false },
    ],
    history: [{ status: "Detected", timestamp: "2026-10-07T12:05:00Z", note: "Incident automatically detected" }],
    created_at: "2026-10-07T12:05:00Z",
    updated_at: "2026-10-07T12:05:00Z",
  },
];

describe("dashboard against incidents API", () => {
  let mockStore;

  beforeEach(() => {
    mockStore = JSON.parse(JSON.stringify(MOCK_INCIDENTS));
    vi.spyOn(globalThis, "fetch").mockImplementation(async (url, opts = {}) => {
      const urlStr = String(url);
      const method = opts.method || "GET";

      if (urlStr.includes("/incidents/") && urlStr.includes("/status") && method === "PATCH") {
        const parts = urlStr.split("/incidents/")[1].split("/status")[0];
        const incident = mockStore.find((i) => i.incident_id === parts);
        if (!incident) return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
        const body = JSON.parse(opts.body);
        incident.status = body.status;
        incident.history.push({ status: body.status, timestamp: new Date().toISOString(), note: body.note || "Status changed by analyst" });
        return { ok: true, status: 200, json: async () => incident };
      }

      if (urlStr.includes("/incidents/") && method === "GET") {
        const id = urlStr.split("/incidents/")[1].split("?")[0];
        const incident = mockStore.find((i) => i.incident_id === id);
        if (!incident) return { ok: false, status: 404, json: async () => ({ detail: "Not found" }) };
        return { ok: true, status: 200, json: async () => incident };
      }

      if (urlStr.endsWith("/incidents") || urlStr.includes("/incidents?")) {
        return { ok: true, status: 200, json: async () => mockStore };
      }

      return { ok: false, status: 404, json: async () => ({ detail: "Route not found" }) };
    });
  });

  it("1. renders verified incidents and severity tile metrics", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(2));
    expect(tileCount("Critical")).toBe("1");
    expect(tileCount("Medium")).toBe("1");
    expect(tileCount("High")).toBe("0");
    expect(tileCount("Low")).toBe("0");
  });

  it("2. severity and status filters work correctly", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(2));
    click(screen.getByTestId("tile-Critical"));
    expect(items()).toHaveLength(1);
    expect(items()[0].textContent).toContain("sg-prod");
    click(screen.getByTestId("tile-Critical"));
    expect(items()).toHaveLength(2);

    click(button(/^Investigating/));
    expect(items()).toHaveLength(0);
    screen.getByText(/No incidents match these filters/);
    click(button(/^Detected/));
    expect(items()).toHaveLength(2);
  });

  it("3. opening an incident loads its details and playbook", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(2));
    click(items().find((el) => el.textContent.includes("sg-prod")));
    await screen.findByRole("heading", { name: "SSH open to the world: sg-prod" });
    screen.getByText("AWS");
    screen.getByText("security_group · sg-prod");
    screen.getByText("AuthorizeSecurityGroupIngress");
    screen.getByText("evt-test-01");
    expect(screen.getAllByText("AWS CloudTrail").length).toBeGreaterThan(0);
    screen.getByText("Inspect the security group.");
  });

  it("4. status changes update incident state and timeline", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(2));
    click(items().find((el) => el.textContent.includes("sg-prod")));
    await screen.findByRole("heading", { name: "SSH open to the world: sg-prod" });

    click(await screen.findByRole("button", { name: "Mark as Investigating" }));
    await waitFor(() => expect(screen.getAllByText("Investigating").length).toBeGreaterThan(0));
  });

  it("5. searches across incident title, actor, and event ID", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(2));
    const search = screen.getByRole("searchbox", { name: "Search incidents" });
    fireEvent.change(search, { target: { value: "evt-test-02" } });
    expect(items()).toHaveLength(1);
    expect(items()[0].textContent).toContain("data-archive");
  });

  it("6. shows proper empty state when database has zero incidents", async () => {
    mockStore = [];
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(0));
    screen.getByText("No incidents yet.");
    screen.getByText("No security incidents detected or imported yet.");
  });

  it("7. shows an error state when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<App />);
    await screen.findByText(/Cannot reach the API/);
    screen.getByRole("alert");
  });
});

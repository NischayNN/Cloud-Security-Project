// End-to-end check: React <App /> -> real FastAPI server -> in-memory store -> engine.
// Use CLOUD_SECURITY_STORE=memory on port 8001; these tests reset its store.
// Run: VITE_API_URL=http://127.0.0.1:8001 npm run test:e2e
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App.jsx";
import { getIncident, getIncidents, postEvent } from "./api.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const items = () => screen.queryAllByTestId("incident-item");
const click = (el) => fireEvent.click(el);
const button = (name) => screen.getByRole("button", { name });
const tileCount = (s) => String(Number(within(screen.getByTestId(`tile-${s}`)).getByText(/^\d+$/).textContent));

describe("dashboard against the live backend", () => {
  beforeEach(async () => {
    const base = import.meta.env.VITE_API_URL;
    if (base !== "http://127.0.0.1:8001") {
      throw new Error("Use a disposable backend: VITE_API_URL=http://127.0.0.1:8001");
    }
    const res = await fetch(base + "/demo/load?reset=true", { method: "POST" });
    if (!res.ok) throw new Error("Could not prepare the test backend");
  });
  it("1. loads demo incidents without creating duplicates", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    click(button("Load demo incidents"));
    await screen.findByText(/Demo already loaded.*no duplicates added/);
    await waitFor(() => expect(items()).toHaveLength(6));
    expect([tileCount("Critical"), tileCount("High"), tileCount("Medium"), tileCount("Low")]).toEqual(["3", "1", "1", "1"]);
  });

  it("2. severity filter and 3. status filter work", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    click(screen.getByTestId("tile-Critical"));
    expect(items()).toHaveLength(3);
    click(screen.getByTestId("tile-Critical"));
    expect(items()).toHaveLength(6);
    click(button(/^Investigating/));
    expect(items()).toHaveLength(0);
    screen.getByText(/No incidents match these filters/);
    click(button(/^Detected/));
    expect(items()).toHaveLength(6);
  });

  it("4. opening an incident loads its details and playbook from the API", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    click(items().find((el) => el.textContent.includes("college-notes")));
    await screen.findByRole("heading", { name: "Public S3 bucket: college-notes" });
    screen.getByText(/public s3 bucket$/);           // incident type
    screen.getByText("AWS");                          // cloud
    screen.getByText("student-dev");                  // actor
    screen.getByText("s3_bucket · college-notes");    // resource
    screen.getByText("PutBucketAcl");
    screen.getByText("evt-0001");
    screen.getByText("Simulated event for demonstration and testing.");                 // event
    screen.getByText(/Why medium \(score 50\)/);
    screen.getByText("Bucket is publicly accessible (+50)");
    for (const t of ["Confirm exposure", "Block public access", "Review access logs", "Document & prevent"]) screen.getByText(t);
    screen.getByText(/aws s3api get-bucket-acl --bucket college-notes/);
  });

  it("5. status changes go through PATCH and update the backend", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    click(items().find((el) => el.textContent.includes("college-notes")));
    await screen.findByRole("heading", { name: "Public S3 bucket: college-notes" });
    const id = (await getIncidents()).find((i) => i.resource_id === "college-notes").incident_id;
    for (const next of ["Investigating", "Contained", "Resolved"]) {
      click(await screen.findByRole("button", { name: `Mark as ${next}` }));
      await waitFor(async () => expect((await getIncident(id)).status).toBe(next));
      await waitFor(() => expect(screen.queryByRole("button", { name: "Saving…" })).toBeNull());
    }
    expect(screen.queryByRole("button", { name: /^Mark as/ })).toBeNull();      // nothing after Resolved
    const inc = await getIncident(id);
    expect(inc.history.map((h) => h.status)).toEqual(["Detected", "Investigating", "Contained", "Resolved"]);
    expect(screen.getAllByText(/Status changed by analyst/)).toHaveLength(3);   // history timeline in the UI
    expect(tileCount("Medium")).toBe("0");                                       // resolved incidents leave the open count
  });

  it("6. a page refresh keeps the backend state", async () => {
    const id = (await getIncidents()).find((i) => i.resource_id === "college-notes").incident_id;
    for (const status of ["Investigating", "Contained", "Resolved"]) {
      await fetch(import.meta.env.VITE_API_URL + `/incidents/${id}/status`, {
        method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }),
      });
    }
    cleanup();
    render(<App />);                                                             // fresh mount = page reload
    await waitFor(() => expect(items()).toHaveLength(6));
    click(button(/^Resolved/));
    expect(items()).toHaveLength(1);
    expect(items()[0].textContent).toContain("college-notes");
    click(items()[0]);
    await screen.findByRole("heading", { name: "Public S3 bucket: college-notes" });
    expect(screen.getAllByText(/^Resolved$/).length).toBeGreaterThan(0);
  });

  it("7. POST /events via api.js creates an incident", async () => {
    const before = (await getIncidents()).length;
    const ev = { eventID: "e2e-1", eventName: "AuthorizeSecurityGroupIngress", eventSource: "ec2.amazonaws.com",
      eventTime: "2026-09-29T09:00:00Z", awsRegion: "ap-south-1", recipientAccountId: "123456789012",
      userIdentity: { userName: "alice" },
      requestParameters: { groupId: "sg-e2e", groupName: "web", ipPermissions: { items: [
        { ipProtocol: "tcp", fromPort: 22, toPort: 22, ipRanges: { items: [{ cidrIp: "0.0.0.0/0" }] } }] } } };
    const res = await postEvent(ev);
    expect(res.detected).toBe(true);
    expect(res.incident.severity).toBe("High");
    expect((await getIncidents()).length).toBe(before + 1);
  });

  it("demo loading preserves separately ingested incidents", async () => {
    const raw = { eventID: "fixture-preserve", eventName: "AttachUserPolicy", eventSource: "iam.amazonaws.com",
      eventTime: "2026-10-06T10:00:00Z", awsRegion: "ap-south-1", recipientAccountId: "123456789012",
      userIdentity: { userName: "fixture-user" }, requestParameters: { userName: "fixture-target",
        policyArn: "arn:aws:iam::aws:policy/AdministratorAccess" } };
    const saved = await postEvent(raw);
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(7));
    click(button("Load demo incidents"));
    await waitFor(() => expect(button("Load demo incidents").disabled).toBe(false));
    expect(items()).toHaveLength(7);
    expect((await getIncident(saved.incident.incident_id)).resource_id).toBe("fixture-target");
  });

  it.each([
    ["aws-cloudtrail", "AWS CloudTrail"],
    ["fixture", "Test fixture"],
    ["submitted", "Submitted / unverified"],
  ])("displays %s origin and event ID", async (origin, label) => {
    const raw = { eventID: `origin-${origin}`, eventName: "AttachUserPolicy", eventSource: "iam.amazonaws.com",
      eventTime: "2026-10-06T10:00:00Z", awsRegion: "ap-south-1", recipientAccountId: "123456789012",
      userIdentity: { userName: "fixture-user" }, requestParameters: { userName: "origin-target",
        policyArn: "arn:aws:iam::aws:policy/AdministratorAccess" } };
    const response = await fetch(import.meta.env.VITE_API_URL + `/events?origin=${origin}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(raw),
    });
    expect(response.status).toBe(201);
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(7));
    click(items().find((el) => el.textContent.includes("origin-target")));
    await screen.findByText(raw.eventID);
    expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    screen.getByText("Playbook steps are manual guidance. Changing status does not execute AWS commands.");
  });

  it("searches event IDs and combines source filters without changing stored incidents", async () => {
    await postEvent({ eventID: "search-evidence-id", eventName: "AttachUserPolicy", eventSource: "iam.amazonaws.com",
      eventTime: "2026-10-06T10:00:00Z", awsRegion: "ap-south-1", recipientAccountId: "123456789012",
      userIdentity: { userName: "search-actor" }, requestParameters: { userName: "search-target",
        policyArn: "arn:aws:iam::aws:policy/AdministratorAccess" } });
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(7));
    const search = screen.getByRole("searchbox", { name: "Search incidents" });
    fireEvent.change(search, { target: { value: "search-evidence-id" } });
    expect(items()).toHaveLength(1);
    expect(items()[0].textContent).toContain("search-target");
    const source = screen.getByRole("combobox", { name: "Filter by source" });
    fireEvent.change(source, { target: { value: "demo" } });
    expect(items()).toHaveLength(0);
    click(button("Clear filters"));
    expect(items()).toHaveLength(7);
    fireEvent.change(source, { target: { value: "other" } });
    expect(items()).toHaveLength(1);
    expect(items()[0].textContent).toContain("Submitted / unverified");
    expect((await getIncidents()).length).toBe(7);
  });

  it("refreshes both the queue and selected details after an external status change", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    click(items().find(el => el.textContent.includes("college-notes")));
    await screen.findByRole("heading", { name: "Public S3 bucket: college-notes" });
    const id = (await getIncidents()).find(i => i.resource_id === "college-notes").incident_id;
    const res = await fetch(import.meta.env.VITE_API_URL + `/incidents/${id}/status`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "Investigating" }),
    });
    expect(res.ok).toBe(true);
    const realFetch = globalThis.fetch;
    let release;
    const gate = new Promise(resolve => { release = resolve; });
    vi.spyOn(globalThis, "fetch").mockImplementation(async (...args) => { await gate; return realFetch(...args); });
    click(button("Refresh"));
    expect(button("Refreshing…").disabled).toBe(true);
    expect(button("Load demo incidents").disabled).toBe(true);
    release();
    await screen.findByText("Dashboard updated. 6 saved incidents loaded.");
    await screen.findByRole("button", { name: "Mark as Contained" });
    expect(items().find(el => el.textContent.includes("college-notes")).textContent).toContain("Investigating");
  });

  it("reports when a refresh succeeds without changes", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    await screen.findByRole("heading", { name: "Public S3 bucket: prod-customer-backup" });
    click(button("Refresh"));
    await screen.findByText("Up to date. 6 saved incidents; no changes since the last refresh.");
    expect(button("Refresh").disabled).toBe(false);
  });

  it("does not show a success message when refresh fails", async () => {
    render(<App />);
    await waitFor(() => expect(items()).toHaveLength(6));
    await screen.findByRole("heading", { name: "Public S3 bucket: prod-customer-backup" });
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    click(button("Refresh"));
    await waitFor(() => expect(button("Refresh").disabled).toBe(false));
    expect(screen.getAllByRole("alert").length).toBeGreaterThan(0);
    expect(screen.getByRole("status").textContent).toBe("");
    expect(items()).toHaveLength(6);
  });

  it("8. shows an error state when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<App />);
    await screen.findByText(/Cannot reach the API/);
    screen.getByRole("alert");
  });
});

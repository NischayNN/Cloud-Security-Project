// End-to-end check: React <App /> -> real FastAPI server -> in-memory store -> engine.
// Start the backend on a FRESH store first:  cd backend && uvicorn app.main:app
// Then run:  npm run test:e2e
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import App from "./App.jsx";
import { getIncident, getIncidents, postEvent } from "./api.js";

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const items = () => screen.queryAllByTestId("incident-item");
const click = (el) => fireEvent.click(el);
const button = (name) => screen.getByRole("button", { name });
const tileCount = (s) => within(screen.getByTestId(`tile-${s}`)).getByText(/^\d+$/).textContent;

describe("dashboard against the live backend", () => {
  it("1. shows the empty state, then loads the 6 demo incidents", async () => {
    render(<App />);
    await screen.findByText("No incidents yet.");
    click(button("Load demo incidents"));
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
    screen.getByText("PutBucketAcl");                 // event
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

  it("8. shows an error state when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    render(<App />);
    await screen.findByText(/Cannot reach the API/);
    screen.getByRole("alert");
  });
});

import {
  render,
  screen,
  fireEvent,
  waitFor,
  cleanup,
} from "@testing-library/react";
import { vi, test, afterEach, expect } from "vitest";
import App from "./App";
const names = ["Stripe", "HubSpot", "Notion", "Resend", "Twilio", "Google"];
const providers = names.map((name) => ({
  id: name.toLowerCase(),
  name,
  mode: "simulated",
  connected: false,
  actions: [
    { id: "success", label: "Success scenario" },
    { id: "failure", label: "Failure scenario" },
  ],
}));
let logged = false;
function mock() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/demo-login")) {
        logged = true;
        return response({
          user: { display_name: "Demo Operator" },
          csrf_token: "token",
        });
      }
      if (url.endsWith("/logout")) {
        logged = false;
        return response({});
      }
      if (url.endsWith("/me"))
        return logged
          ? response({
              user: { display_name: "Demo Operator" },
              csrf_token: "token",
            })
          : response({}, 401);
      if (url.endsWith("/integrations"))
        return response({ integrations: providers });
      if (url.endsWith("/activity")) return response({ events: [] });
      return response({
        provider: "stripe",
        status: "success",
        mode: "simulated",
        reference: "demo-123",
        message: "Synthetic checkout completed.",
      });
    }),
  );
}
function response(data: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  logged = false;
});
test("synthetic sign-in opens all six provider controls, runs a fixture and signs out", async () => {
  mock();
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Enter demo workspace" }),
  );
  for (const name of names)
    expect(await screen.findByRole("heading", { name })).toBeInTheDocument();
  fireEvent.click(
    screen.getByRole("button", { name: "Stripe: Success scenario" }),
  );
  expect(await screen.findByText("demo-123")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
  expect(
    await screen.findByRole("button", { name: "Enter demo workspace" }),
  ).toBeInTheDocument();
});
test("network failure is visible and allows retry", async () => {
  mock();
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Enter demo workspace" }),
  );
  await screen.findByRole("heading", { name: "Stripe" });
  vi.mocked(fetch).mockRejectedValueOnce(new Error("offline"));
  fireEvent.click(
    screen.getByRole("button", { name: "Stripe: Failure scenario" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Unable to reach the local demo server",
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Stripe: Failure scenario" }),
    ).toBeEnabled(),
  );
});
test("security rejection is visible, and expired sessions clear protected content", async () => {
  mock();
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Enter demo workspace" }),
  );
  await screen.findByRole("heading", { name: "Stripe" });
  vi.mocked(fetch).mockResolvedValueOnce(response({}, 403) as Response);
  fireEvent.click(
    screen.getByRole("button", { name: "Stripe: Success scenario" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Request rejected by the local security checks",
  );
  await waitFor(() =>
    expect(
      screen.getByRole("button", { name: "Stripe: Success scenario" }),
    ).toBeEnabled(),
  );
  vi.mocked(fetch).mockResolvedValueOnce(response({}, 401) as Response);
  fireEvent.click(
    screen.getByRole("button", { name: "Stripe: Success scenario" }),
  );
  expect(
    await screen.findByRole("button", { name: "Enter demo workspace" }),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("heading", { name: "Stripe" }),
  ).not.toBeInTheDocument();
});
test("failed fixture shows expected failure and session activity", async () => {
  mock();
  render(<App />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Enter demo workspace" }),
  );
  await screen.findByRole("heading", { name: "Stripe" });
  const event = {
    provider: "stripe",
    action: "failure",
    status: "failed",
    mode: "simulated",
    reference: "demo-failure",
    message: "Synthetic payment declined.",
  };
  vi.mocked(fetch)
    .mockResolvedValueOnce(response(event) as Response)
    .mockResolvedValueOnce(response({ integrations: providers }) as Response)
    .mockResolvedValueOnce(response({ events: [event] }) as Response);
  fireEvent.click(
    screen.getByRole("button", { name: "Stripe: Failure scenario" }),
  );
  expect(
    await screen.findByRole("heading", { name: "Failure scenario reproduced" }),
  ).toBeInTheDocument();
  expect(await screen.findByText("Expected failure")).toBeInTheDocument();
  expect(screen.getAllByText("demo-failure")).toHaveLength(2);
});

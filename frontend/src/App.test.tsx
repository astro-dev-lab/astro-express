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
function mock(mode: "simulation" | "production" = "simulation", role = "admin") {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/config")) return response({mode, credential_login: mode === "production"});
      if (url.endsWith("/demo-login") || url.endsWith("/login")) {
        logged = true;
        return response({
          user: { display_name: "Demo Operator", role },
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
              user: { display_name: "Demo Operator", role },
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

test("production sign-in requires credentials and preserves administrator controls", async () => {
  mock("production"); render(<App />);
  const username = await screen.findByLabelText("Username");
  const password = screen.getByLabelText("Password");
  expect(screen.queryByRole("button", {name:"Enter demo workspace"})).not.toBeInTheDocument();
  expect(username).toBeRequired(); expect(password).toBeRequired();
  fireEvent.change(username,{target:{value:"fixture-admin"}});
  fireEvent.change(password,{target:{value:"synthetic-password"}});
  fireEvent.click(screen.getByRole("button",{name:"Sign in"}));
  await screen.findByRole("heading",{name:"Stripe"});
  expect(fetch).toHaveBeenCalledWith("/api/auth/login",expect.objectContaining({body:JSON.stringify({username:"fixture-admin",password:"synthetic-password"})}));
  expect(screen.getByRole("button",{name:"Stripe: Success scenario"})).toBeEnabled();
});
test("invalid credentials give generic error and clear password", async () => {
  mock("production"); render(<App />);
  fireEvent.change(await screen.findByLabelText("Username"),{target:{value:"fixture-user"}});
  fireEvent.change(screen.getByLabelText("Password"),{target:{value:"synthetic-password"}});
  vi.mocked(fetch).mockResolvedValueOnce(response({detail:"must not reveal user existence"},401) as Response);
  fireEvent.click(screen.getByRole("button",{name:"Sign in"}));
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to sign in. Check your credentials and try again.");
  expect(screen.getByLabelText("Password")).toHaveValue("");
});
test("viewer can read six cards but cannot execute any scenario", async () => {
  logged=true; mock("production", "viewer"); render(<App />);
  await screen.findByRole("heading", {name:"Stripe"});
  expect(screen.getByText("Read-only access. An administrator can run simulation scenarios.")).toBeInTheDocument();
  for(const name of names) for(const label of ["Success scenario","Failure scenario"])
    expect(screen.getByRole("button", {name:`${name}: ${label}`})).toBeDisabled();
});

test("configuration failure cannot expose either sign-in route", async () => {
  mock();
  vi.mocked(fetch).mockRejectedValueOnce(new Error("offline"));
  render(<App />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to reach the local demo server");
  expect(screen.queryByRole("button", { name: "Enter demo workspace" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Sign in" })).not.toBeInTheDocument();
  expect(screen.getByText("Sign-in configuration unavailable.")).toBeInTheDocument();
});

test("production cards distinguish unconfigured real sandbox tests from regression fixtures", async () => {
  logged = true;
  mock("production");
  render(<App />);
  await screen.findByRole("heading", { name: "Stripe" });
  expect(screen.getAllByText("SANDBOX NOT CONFIGURED")).toHaveLength(6);
});

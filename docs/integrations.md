# Offline fixture catalog

Every response reports `mode: simulated`. Provider listings report `connected: false`. Each result has a unique `demo-` reference and appears only in the invoking session history.

| Provider | Success | Failure | External effect |
|---|---|---|---|
| Stripe | Checkout succeeded | Payment declined | No charge |
| HubSpot | Contact qualified | Duplicate contact | No CRM write |
| Notion | Page created | Permission denied | No workspace write |
| Resend | Email queued | Bounced | No email |
| Twilio | SMS queued | Invalid number/rejected | No SMS or call |
| Google | Calendar event created | Authorization rejected | No OAuth or calendar write |

Actions accept only a fixture identifier, never an email, phone number, account token, card number, or arbitrary provider payload. No sandbox/live toggle or automatic fallback exists. Failure outcomes are fixtures rather than evidence of vendor behavior. Tests verify both outcomes for every provider.

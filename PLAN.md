# Development plan

Ruin Everything gives browser agents a local execution environment for tasks that span sign-in, verification and submission. Each adapter defines how to recognize its original tab, what to do when work is interrupted, and what counts as completion.

## Milestones

![Four illustrated milestones: session layers, a credential lock, a verification envelope and a flag for write outcomes.](docs/figures/roadmap.svg)

| Area | Implemented | Further acceptance work |
| --- | --- | --- |
| Session reuse | Shared local Chrome via CDP and a dedicated persistent profile | Verify that revoking task access prevents navigation. |
| Credential filling | Same-origin keyring lookup and local fill | Exercise origin changes with test credentials and inspect model input and logs for leakage. |
| Verification | Interactive sign-in, origin-bound TOTP and an Outlook Web watcher for Greenhouse | Distinguish expired codes, denied challenges and device recovery. Validate email matching across supported Outlook layouts. |
| Write operations | Single-tab click loop and an Ashby receipt journal | Define permitted targets, duration and revocation for payments, deletions and public sends. Simulate a lost submission response and verify recovery without duplication. |

Ashby receipt lookup and observation are available through local MCP tools. Upcoming design decisions include which other adapters to expose and how users should grant and revoke action-specific permissions.

## Adapter example: Duke Canvas

![Persistent browser data and the two possible paths to the course list.](docs/figures/session.svg)

The course lookup targets Duke University's main Canvas instance. A valid session should return accessible course links directly. If redirected, keep the query alive during sign-in and retry the course page once. If the retry redirects again, stop and report the loop. An empty course table should yield an empty result.

Future recovery work includes distinguishing a denied challenge from a timeout, helping users reconnect a replacement phone, and explaining missing courses or a different school instance. Duke's remembered-device option applies to the same browser and computer for five days when offered. [Student guide](https://go.canvas.duke.edu/students/) · [MFA help](https://idms-mfa.oit.duke.edu/mfa/help) · [Canvas support](https://go.canvas.duke.edu/get-help/)

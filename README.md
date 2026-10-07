# MTG Vibes

A Commander workspace with deck-list import, basic deck analysis, manual opening-hand testing, Scryfall lookups, and optional OpenAI chat.

## Run locally

Requires Python 3.12+; no packages to install.

```sh
cd /workspace/MTG-Vibes
python server.py
```

The development server binds to loopback on port 8000. Set `MTG_SITE_PASSWORD` to enable browser password authentication (username `stwizz`). Public binding is refused without this password. Render terminates HTTPS; the container runs a small Python server suitable for this personal prototype. This is not a multi-user production service.

## Get a website URL with Render

1. Sign in at https://dashboard.render.com and connect your GitHub account. Allow access to `sthixon22-ux/MTG-Vibes`.
2. Select **New → Blueprint**, choose that repository and the `main` branch, and use its `render.yaml` file.
3. Enter your OpenAI key in Render's secure `MTG_OPENAI_API_KEY` environment setting. Never put it in GitHub or chat. For deck tools without AI, use a regular Web Service with Docker and omit this optional key.
4. Deploy the Blueprint. It creates a free web service; confirm the currently offered plan and pricing in Render before proceeding. Free services can take time to wake after inactivity.
5. Open the service's **Environment** settings to retrieve the generated `MTG_SITE_PASSWORD`, or replace it securely with your own password. Login username is `stwizz`.
6. Wait for **Live**, then open the HTTPS URL shown on the service page. Render chooses the actual hostname; a URL has not been allocated just by saving these files.

This browser login protects both the website and its AI endpoints. `/healthz` exposes only service readiness for Render. AI requests are limited to 10 per minute across the service. Set an OpenAI project budget as appropriate. Closing all private browser windows clears their browser authentication session.

The OpenAI key in the Codex cloud environment does not automatically move to Render; configure it separately there. No hosting credential or subscription is required to run locally. No Render deployment has been performed by these files alone.

## Use

Click **Add a deck**, open your linked Moxfield deck, export its text list, and paste or upload the export in **My decks**. Include the commander in the list and enter its name separately. Click **Save deck & analyze**. Up to 30 decks are saved in browser local storage. Use the saved-deck selector to switch lists, **Download list** for backups, and **Delete deck** to remove a local copy. Decks do not sync between devices, and deleting a deck never changes Moxfield. Sideboard and maybeboard sections are excluded. The initial version supports one commander; partner/background configurations need a later implementation.

Basic analysis checks the total count, commander presence, and potential duplicates. Fetch Scryfall data for confirmed land counts. It does not yet validate all Commander legality or classify ramp, removal, and synergy. Partial metadata is explicitly labeled.

Opening hands exclude one copy of the selected commander. The first multiplayer mulligan is free; later mulligans require selecting cards to bottom. Draws consume cards without replacement. This is a manual tester, not a complete rules engine.

Chat commands: `import my deck`, `analyze my deck`, `test an opening hand`, and `find Sol Ring`. Other messages go to OpenAI when configured. Libby receives the active deck, analysis, fetched card metadata, current hand and board, and the last ten conversation exchanges. Follow-up questions retain context until you start a new conversation or end the browser tab session. Chat history is saved per deck in session storage in this browser tab; it is sent to OpenAI with each follow-up. It has no live browsing or account access and cannot alter the deck.

## Optional AI configuration

Configure `MTG_OPENAI_API_KEY` securely in the environment; never commit it. `MTG_OPENAI_MODEL` optionally overrides `gpt-4.1-mini`. The server uses the OpenAI Responses API with `store: false`. Model requests occur when you send a message or select an AI analysis action. This setting does not establish a zero-retention agreement with the provider.

Required network hosts: `api.scryfall.com`, `api.openai.com`. Manual source links go to Moxfield, Scryfall, and EDHREC. No automated Moxfield or EDHREC integration is implemented; supported access and terms must be verified before adding one. Never collect Moxfield passwords.

## Validation

Run `python -m unittest discover -s tests -v` and `node tests/deck.test.cjs` (Node 18+ for this test only). Tests cover server health, request validation, missing credentials, mocked Scryfall/OpenAI responses, deck parsing, commander exclusion, mulligans, and draws. Live API validation requires the network policy and, for OpenAI, a usable credential.

## Card images and deck source links

Playtesting automatically fetches Scryfall images for cards in hand. Click a card to enlarge it (including both faces where available); when bottoming after a mulligan, clicking selects the card to bottom instead. Failed image loads leave the card name usable. **Ask AI about this hand** supplies the real hand for discussion.

Each deck has an optional **Moxfield deck URL** field. Save the deck after entering its source URL; both Moxfield links then follow the active deck. Old saved lists without a source URL link to the Moxfield homepage until you add one. Adding a URL does not automatically import or synchronize that deck.

After a GitHub update, use Render → mtg-vibes → **Manual Deploy → Deploy latest commit** and wait for **Live**. Automatic deploy is disabled in the Blueprint.

## Libby and the goldfish table

Click the animated cube on the homepage to start talking to Libby. Choose a saved deck in the sidebar to supply its full list. Libby receives that list, local analysis, and the current hand and board when present; it cannot directly read your Moxfield account. External Moxfield navigation goes to its homepage for sign-in.

The separate `/playtest` page provides library, hand, battlefield, command zone, graveyard, and exile. Select a card, then use the move buttons; battlefield cards can tap and carry counters. Life, tokens, turn advance, top-card viewing, milling, library shuffling, and up to 50 undo snapshots are available. Multiplayer mulligans start with one free mulligan. New game clears the table. Game state survives navigation within the same browser tab; switching active decks resets the table. This is a manual goldfishing tool, not a rules engine.

Images now use the authenticated `/api/card-image` route. The server retrieves approved Scryfall JPEGs and caches them in the ignored `.card-images/` directory; the browser loads them from the app origin. Retry images is available when downloads fail. Render may clear this cache during redeployments.

OpenAI 429 errors are categorized: insufficient quota requires checking API credits, billing, and project limits; temporary provider rate limits advise waiting. Site rate limits are separate. These messages do not repair missing API quota, and ChatGPT subscriptions do not supply API credits.

## Focused workspace and controls

The homepage is Libby chat. `/upload` is deck import and editing; `/analyze` has image, text, and statistics views; `/playtest` is a fitted goldfishing workspace with a persistent hand tray. Large lists scroll within their own panels rather than extending the whole page. The theme uses navy, violet, and warm accents.

Drag a card between hand, battlefield, graveyard, exile, command zone, or library. A library drop puts the card on top; Shift-drop puts it on the bottom. Touch dragging and click-plus-move controls are also available. Hover hotkeys: P battlefield, H hand, G graveyard, X exile, L library top, B library bottom, C command, T tap/untap, V enlarge, +/- counters. Global D draws, N advances turn, and U undoes. Hotkeys do not run inside text fields or the card viewer.

In Upload decks, select a cover card or upload PNG/JPEG/WebP artwork under 5 MB. Custom artwork is resized locally and saved with the deck in this browser; it is not sent to OpenAI. Browser storage can fill; keep deck-list backups. These text backups do not include artwork.

Statistics use Scryfall metadata, counting front-face lands separately from flexible land back faces. The standard opening-hand check reports exact probabilities of exactly or at least three lands plus a nonland spell with mana value at most two in seven cards, before mulligans. Commander is excluded. Incomplete card data never produces invented odds. These calculations work without an OpenAI key or available quota. Free-form AI conversation still requires usable OpenAI API credentials and quota.

**Check AI** sends one short model request and reports the result. An unclassified provider 429 is not labeled temporary. Check API billing/usage and the key’s project when quota is unavailable. The optional browser regression test is `PLAYWRIGHT_BROWSERS_PATH=/tmp/mtg-playwright python tests/browser_smoke.py` with Playwright, its Chromium browser, and Pillow installed; set MTG_TEST_URL to the running development server.

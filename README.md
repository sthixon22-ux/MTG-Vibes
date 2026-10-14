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

Click **Add a deck**, open your linked Moxfield deck, export its text list, and paste or upload the export in **My decks**. Include the commander in the list and enter its name separately. Click **Save deck & analyze**. Up to 30 decks are saved in browser local storage. Use the saved-deck selector to switch lists, **Download list** for backups, and **Delete deck** to remove a local copy. Decks do not sync between devices, and deleting a deck never changes Moxfield. Sideboard and maybeboard sections are excluded. Enter an optional second commander for compatible Partner, named Partner, Background, or Doctor configurations. Include both in the list; both start in the command zone and are excluded from the library.

Refresh card data to check the 100-card total, commander eligibility/pair compatibility, singleton and Oracle copy exceptions, Commander legality, and color identity using Scryfall. Identity includes all faces and colored symbols, not just card color. Basic land types are checked separately. Missing data and unsupported pregame color choices prevent verified additions. Construction checks do not certify every companion condition or unusual restriction, and Rule 0 needs individual review.

Opening hands exclude one copy of the selected commander. The first multiplayer mulligan is free; later mulligans require selecting cards to bottom. Draws consume cards without replacement. This is a manual tester, not a complete rules engine.

Chat commands: `import my deck`, `analyze my deck`, `test an opening hand`, and `find Sol Ring`. Other messages go to OpenAI when configured. Libby receives the active deck, analysis, fetched card metadata, current hand and board, and the last ten conversation exchanges. Follow-up questions retain context until you start a new conversation or end the browser tab session. Chat history is saved per deck in session storage in this browser tab; it is sent to OpenAI with each follow-up. It can research public Magic strategy with cited web search and EDHREC commander data. It has no private account access and cannot alter the deck.

## Optional AI configuration

Configure `MTG_OPENAI_API_KEY` securely in the environment; never commit it. `MTG_OPENAI_MODEL` optionally overrides `gpt-5.4`. The server uses the OpenAI Responses API with `store: false`. Model requests occur when you send a message or select an AI analysis action. This setting does not establish a zero-retention agreement with the provider.

Required network hosts: `api.scryfall.com`, `api.openai.com`. Manual source links go to Moxfield, Scryfall, and EDHREC. No automated Moxfield or EDHREC integration is implemented; supported access and terms must be verified before adding one. Never collect Moxfield passwords.

## Validation

Run `python -m unittest discover -s tests -v` and `node tests/deck.test.cjs` (Node 18+ for this test only). Tests cover server health, request validation, missing credentials, mocked Scryfall/OpenAI responses, deck parsing, commander exclusion, mulligans, and draws. Live API validation requires the network policy and, for OpenAI, a usable credential.

## Card images and deck source links

Playtesting automatically fetches Scryfall images for cards in hand. Click a card to enlarge it (including both faces where available); when bottoming after a mulligan, clicking selects the card to bottom instead. Failed image loads leave the card name usable. **Ask AI about this hand** supplies the real hand for discussion.

Each deck has an optional **Moxfield deck URL** field. Save the deck after entering its source URL; both Moxfield links then follow the active deck. Old saved lists without a source URL link to the Moxfield homepage until you add one. Adding a URL does not automatically import or synchronize that deck.

After a GitHub update, use Render → mtg-vibes → **Manual Deploy → Deploy latest commit** and wait for **Live**. Automatic deploy is disabled in the Blueprint.

## Libby and the goldfish table

Click Libby’s animated spirit familiar on the homepage to start talking to Libby. Choose a saved deck in the sidebar to supply its full list. Libby receives that list, local analysis, and the current hand and board when present; it cannot directly read your Moxfield account. External Moxfield navigation goes to its homepage for sign-in.

The separate `/playtest` page provides library, hand, battlefield, command zone, graveyard, and exile. Select a card, then use the move buttons; battlefield cards can tap and carry counters. Life, tokens, turn advance, top-card viewing, milling, library shuffling, and up to 50 undo snapshots are available. Multiplayer mulligans start with one free mulligan. New game clears the table. Game state survives navigation within the same browser tab; switching active decks resets the table. This is a manual goldfishing tool, not a rules engine.

Images now use the authenticated `/api/card-image` route. The server retrieves approved Scryfall JPEGs and caches them in the ignored `.card-images/` directory; the browser loads them from the app origin. Retry images is available when downloads fail. Render may clear this cache during redeployments.

OpenAI 429 errors are categorized: insufficient quota requires checking API credits, billing, and project limits; temporary provider rate limits advise waiting. Site rate limits are separate. These messages do not repair missing API quota, and ChatGPT subscriptions do not supply API credits.

## Focused workspace and controls

The homepage is Libby chat. `/upload` is deck import and editing; `/analyze` has image, text, and statistics views; `/playtest` is a fitted goldfishing workspace with a persistent hand tray. Large lists scroll within their own panels rather than extending the whole page. The theme uses navy, violet, and warm accents over original ancient-spire fantasy artwork, with a luminous library spirit for Libby.

Drag a card between hand, battlefield, graveyard, exile, command zone, or library. A library drop puts the card on top; Shift-drop puts it on the bottom. Touch dragging and click-plus-move controls are also available. Hover hotkeys: P battlefield, H hand, G graveyard, X exile, L library top, B library bottom, C command, T tap/untap, V enlarge, +/- counters. Global D draws, N advances turn, and U undoes. Hotkeys do not run inside text fields or the card viewer.

In Upload decks, select a cover card or upload PNG/JPEG/WebP artwork under 5 MB. Custom artwork is resized locally and saved with the deck in this browser; it is not sent to OpenAI. Browser storage can fill; keep deck-list backups. These text backups do not include artwork.

Statistics use Scryfall metadata, counting front-face lands separately from flexible land back faces. The standard opening-hand check reports exact probabilities of exactly or at least three lands plus a nonland spell with mana value at most two in seven cards, before mulligans. Commander is excluded. Incomplete card data never produces invented odds. These calculations work without an OpenAI key or available quota. Free-form AI conversation still requires usable OpenAI API credentials and quota.

**Check AI** sends one short model request and reports the result. An unclassified provider 429 is not labeled temporary. Check API billing/usage and the key’s project when quota is unavailable. The optional browser regression test is `PLAYWRIGHT_BROWSERS_PATH=/tmp/mtg-playwright python tests/browser_smoke.py` with Playwright, its Chromium browser, and Pillow installed; set MTG_TEST_URL to the running development server.

## Verified Commander guidance

Libby receives server-fetched Oracle text and all card faces for the active list, and a construction report rather than trusting browser-provided analysis. OpenAI Responses function tools provide exact Scryfall lookup, identity-filtered candidate searches, and local official-rules retrieval. A structured reply separates proposed additions from conversational analysis. The server checks each addition again for Commander legality, commander color identity, existing cards, and valid proposed cuts. Valid additions survive when another suggestion fails; unsupported cuts are omitted. Rejected or questions-only drafts get up to two repair attempts within a bounded five-request/twelve-tool budget. If the model still avoids giving requested suggestions, Libby presents a balanced set of actual verified candidate cards, with Oracle text instead of invented synergy. Missing card data fails closed. This improves grounding; model strategy and complex rulings can still be mistaken and should be checked against the cited rules.

The bundled official comprehensive rules snapshot is effective **September 25, 2026**, retrieved from https://magic.wizards.com/en/rules and https://media.wizards.com/2026/downloads/MagicCompRules%2020260925.txt. Libby includes standard Commander and partner rules directly, and can retrieve other numbered rules. Update the rules snapshot deliberately when Wizards publishes revisions. Scryfall metadata caches expire after one hour; current Commander legality comes from that metadata rather than a hard-coded ban list. Legendary Vehicle/eligible Spacecraft commander eligibility follows this snapshot. Brawl, Draft, and Duel Commander are distinct formats.

Tests also exercise off-color hybrid/activated/devoid/back-face identities, reminder-text identity, typed lands, banned cards, copy exceptions, incompatible pairs, missing metadata, guarded model drafts, and rules tool conversations. No API credits are needed for construction checks or opening-hand statistics. AI conversations still require an OpenAI API key with available quota.

## Yawgatog rules and voice conversations

Libby’s rules retrieval now includes the September 25, 2026 [Yawgatog hyperlinked Comprehensive Rules](https://yawgatog.com/resources/magic-rules/), matching the bundled official revision. The checked-in JSON contains 3,165 numbered entries and exact anchors. Rules mentioned in a reply appear as clickable Yawgatog references. This is retrieval and rules grounding, rather than model fine-tuning. Refresh both snapshots deliberately when rules revisions change; official Wizards rules take precedence.

On the Libby homepage, click **Talk to Libby** and grant microphone permission. Speak your question, pause, and Libby sends it through the same saved-deck context, history, rules tools, and color-identity checks as typed chat. Replies use the device’s speech-synthesis voice. Libby stops listening during playback, resumes after the reply, and supports **Interrupt** and **End voice**. **Read replies aloud** also reads typed-chat replies. Choose a device voice under **Voice**; voices vary by browser and operating system. This is a turn-based voice conversation, not the OpenAI Realtime/ChatGPT Voice service.

Chrome/Edge browser speech recognition is used when available. The browser’s speech service may process audio externally. If unavailable or its service fails, MediaRecorder records an utterance (silence detection, 60-second/6-MB cap) and the authenticated `/api/transcribe` endpoint sends it to OpenAI’s `whisper-1` transcription API. This fallback incurs API transcription usage in addition to chat usage. Microphone permission and a secure HTTPS origin are required. Audio is kept only in memory for the request and is not written to disk. The server key stays on the server. Ending voice, leaving the page, hiding the tab, or changing decks releases the microphone. Input/provider failures stop voice with a readable error; text chat stays available.

Voice browser regression: start the development server and run `MTG_TEST_URL=http://127.0.0.1:8008 PLAYWRIGHT_BROWSERS_PATH=/tmp/mtg-playwright python tests/browser_voice.py`. It uses synthetic speech/microphone fixtures and mocked chat/transcription, so it checks the conversation lifecycle without paid API calls or real-device audio. Python tests also cover transcription payloads, upload bounds, authentication, origin protection, rate limiting, and Yawgatog links. Actual microphone quality and device voices require testing on the target browser.

## Magic strategy research and conversational advice

Libby has an explicit Magic vocabulary/archetype guide and gives actionable recommendations before asking optional preference questions. Unless you specify otherwise, it assumes casual multiplayer and preserves your commander/theme. Requests for improvements prepare identity-checked ramp, draw, interaction, or requested-role candidates before the model responds. Public EDHREC commander data supplies commander-specific candidates and community usage context; Scryfall independently checks every candidate. Popularity and synergy scores are not legality checks or win-rate claims. Generic “cheap/budget/affordable” requests initially filter suggestions to available Scryfall USD prices of $5 or less; these are indicative prices, not purchase quotes.

The `research_magic` tool uses OpenAI hosted web search for public EDHREC articles, MTGGoldfish builds, Command Zone episode pages/public transcripts, and other Magic sources. Retrieved citations appear below replies. A separate search request avoids mixing hosted search with the strict card-recommendation schema. It uses `MTG_OPENAI_RESEARCH_MODEL` when set, otherwise the chat model; that model must support hosted web search. Search adds OpenAI API usage/tool charges and may add latency. Public research summaries and EDHREC data are cached for one hour. The research prompt asks for commander/topic queries without personal deck lists, profile URLs, or usernames.

This adds references and tools rather than fine-tuning a model on publishers’ content. Access is limited to available public material; it cannot read private accounts, bypass blocked/paywalled sites, or listen to unavailable podcast audio. For example, direct MTGGoldfish article requests can return HTTP 403; Libby can use available indexed public research and continues with verified card data when research fails. Strategy sources cannot override official Commander rules or Scryfall color identity. Model strategy and complex interactions still require judgment; these checks do not guarantee every conversation is correct.

## Cutting a deck down to size

Libby distinguishes requests to remove/trim cards from requests for new additions. For example, “remove 13 cards so this deck has 100” uses the complete selected list and server-counted total, produces a structured cut plan, and checks that the removed quantities bring 113 cards to 100 including commanders. Every proposed cut must be a verified card already in that list, within its available quantity; selected commanders and duplicate cuts are rejected. New-card searches and EDHREC additions are skipped for cuts-only requests. Failed or incomplete plans get bounded repair attempts and never fall back to new additions. Advice does not automatically edit the saved deck.

The full list is supplied separately from Oracle metadata. A missing Scryfall result is reported by card name rather than as loss of access to the whole deck. Cuts needing unknown abilities are withheld. These checks verify membership and arithmetic, not the subjective strategic quality of every proposed cut.

## Named-card evidence and factual review

Libby prefetches recognized named-card questions from Scryfall (quoted names, common evaluation phrasing, and active-list names) before drafting. Corrections referring to “that card” reuse the last user-named card. Its response schema also lists every discussed card: new names first introduced by a draft are fetched and the draft is regenerated with actual evidence. This is bounded; missing data produces a source-only response instead of guessed abilities. Exact English names are required; ambiguous names, spelling errors and unsupported phrasing can require clarification.

Card evaluations and card-specific cut/recommendation reasons get an independent structured factual review against server-fetched Oracle text, all faces, colors, identity, stats, the active list, and available rules/research evidence. A few conservative deterministic checks also reject explicit single-card color, upkeep, and forced-sacrifice contradictions. Failed reviews get bounded repair attempts; persistent failures or review outages withhold the generated evaluation and show actual card data. This is a second model check, not a proof of correctness or a guarantee against every hallucination. Successful named-card discussions display an expandable Scryfall reference and source link.

The reviewer uses `MTG_OPENAI_VERIFY_MODEL` if configured, otherwise `gpt-4.1`, with `store: false`. It adds an API request and latency to card-specific conversations; retries can add more. Do not set it to a model without structured-output support. Creator-inspired strategy means balanced evaluation of curve, mana, setup, multiplayer play and tradeoffs; Libby does not impersonate creators or invent their opinions. Specific attributed views require retrieved public sources.

Natural-language replacement requests such as “change 5 cards in the current deck to 5 different cards” are handled as exactly five one-for-one swaps. Each addition must pass Commander checks and each distinct cut must be an existing noncommander card. Incomplete plans get bounded repairs and never fall back to a generic three-card addition list. Up to twenty swaps are supported per reply. Generic question fragments after “would/is” are no longer treated as card names; actual named-card evidence and factual review remain required.

## Conversation quality and model configuration

The main model now defaults to **GPT-5.4** using the Responses API with low reasoning effort and a larger output budget. Render’s existing `MTG_OPENAI_MODEL` value overrides the default: update that setting to `gpt-5.4`, then deploy the latest commit. The Blueprint also specifies GPT-5.4 for new/synced setups. The homepage reports the configured model (configuration is not proof of working API access). GPT-5.4 uses more API credits than the prior mini model; check your project’s model access and budget. There is no automatic silent downgrade. This is an API model with retrieved Magic references, not this Codex assistant’s training or a fine-tuned Magic model.

“Try again, don’t cut lands” preserves the earlier swap/cut request and enforces the land preference before factual review. State is saved per deck in this browser tab, separately from the bounded transcript, so the preference survives reload and history truncation. A new conversation clears it. Users can explicitly allow land cuts again. The backend validates saved state and still independently checks all card facts and deck membership.

Factual review can now return a corrected reply, preserving valid strategic advice and the user’s requested count, rather than discarding the entire conversation. Corrected plans are checked again for constraints, names, Commander legality and swap/cut counts. If correction remains impossible, the response states that limitation briefly and keeps source text in expandable references for plan requests. A review outage still does not license invented card abilities. Live model quality must be evaluated separately from mocked regression tests.

## Reliable card loading

The deck browser loads Scryfall metadata in collection batches (up to 75 names per request) while rendering the gallery immediately. Refresh card data forces a fresh analysis and recreates failed image elements. Curly apostrophes and extra whitespace are normalized, and double-faced card names share cached metadata with their faces. No fuzzy substitution is used.

Named, collection and search requests share pacing and bounded retries for rate limits and temporary server/network failures. A short cooldown prevents an outage from becoming a long failed request for every card; valid cached cards remain available during slow requests. Concurrent lookups of the same card share one upstream request. Image downloads and gallery images also retry temporary failures. Temporary connection failures are reported separately from a genuine not-found result. Card legality/color checks still use actual Scryfall metadata.

A rejected or failed collection POST no longer disables individual named-card GETs; cooldowns are scoped to the failed endpoint. The gallery renders immediately while metadata checks run in the background. Deck analysis uses one consistent metadata snapshot, and connection failures return a source-error response rather than publishing a false missing-card/construction report. Missing commander metadata does not establish that the commander is absent from the imported list. Existing incomplete failure reports are cleared when a refresh fails; card lists are preserved. Authenticated health diagnostics include the last Scryfall endpoint/error status, and public health exposes the deployed revision for troubleshooting. Local success does not establish that a particular hosting service can reach Scryfall.

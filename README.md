# Next up

Next up suggests practice maps for osu!standard on lazer, using clean passes, recent failures and difficulty calculated with the selected mods. Its music-player interface shows a small map list and an accuracy goal, with normal-speed trials when the available evidence supports them.

Players can enter their osu! ID and sign in through osu!'s authorization page. Each session has its own recommendations and feedback, and passwords are entered only on osu!'s website. The application requests the `public` and `identify` permissions, which provide the signed-in profile and public gameplay data.

Run the Python service with the included Render configuration or another Python host. Set `APP_URL` to the service's HTTPS address and register `/auth/callback` at that address as the osu! application's callback. Store `OSU_CLIENT_ID`, `OSU_CLIENT_SECRET` and `SESSION_SECRET` as host environment secrets, and use one server worker because session state is held in memory. The public files contain no player profile or saved recommendation list.

Tokens and calculated lists remain in server memory and expire after six hours without activity. Signing out removes the session, and server restarts require players to sign in again. Non-credential difficulty preferences and feedback are stored in the player's browser by account. Cached beatmap files contain public map data and can be discarded.

A free Render service sleeps when unused, so its first visit may take about a minute. The source can move to another Python host, while saved browser preferences remain available on the same website origin. No hosting service promises permanent availability.

Beatmap buttons open `osu://b/<ID>`. Players still need to apply the displayed mods in lazer. The suggestions use aggregate map attributes, so replay-level pattern diagnosis remains outside the current algorithm.

# Recommendation model

The same rules apply to every account. The bundled catalogue is sampled across community mod combinations, base difficulty bands, reading settings and short/long maps, independently of any player's history. Public map/mod difficulty and lazer FC pp curves are calculated with rosu-pp-py before deployment.

## Evidence and uncertainty

The service initially reads the top 100 scores and latest 100 recent scores, including failures, then checks up to four further recent pages in the background. Available recent results are merged within the private server session, up to 2,000 observations. This is API-visible history, not an archive of every local or unsubmitted play. Up to 24 uncatalogued reference maps are calibrated per sync, with 16 places reserved for top plays and eight for recent passes and failures. Mod and difficulty buckets preserve diversity, and partial improvements are published after every six newly learned references. Matching coverage is shown because scores without calculated reference features cannot inform physical-demand comparisons.

Recent outcomes carry exponential age weights with a 45-day scale and a small historical floor. Stable historical scores receive half the weight of lazer results. Identical score IDs are deduplicated; at most four observations per map and mod setup are retained with reduced weight for repeated retries so one spammed map does not dominate. Predictions compare the nearest twelve observations in the same effective mod configuration. Early quits, identified by incomplete judgement counts, carry reduced pass-outcome evidence and do not supply complete-map accuracy.

Success envelopes use ordinary passes at 90% or higher with limited miss density rather than requiring two near-FCs in every mod. Reading is matched around demonstrated successful conditions, without a fixed minimum AR or a DT-to-NM assumption. Farm requires near-FC evidence (passed, at least 92% accuracy, limited misses and at least 90% combo coverage), with separate burst and sustained-stream envelopes; Practice can introduce one modest increase. Sparse matches are explicitly marked as trials. Failure outcomes lower pass and FC forecasts. User caps, blocked maps and mod-specific feedback remain hard constraints.

The pass/FC figures are smoothed local heuristics, not statistically calibrated probabilities. Accuracy ranges describe variation in neighbouring outcomes, not confidence intervals. A large or selective top-score history can still create optimism; independent prospective validation remains necessary.

## Farm

A target must exceed the known top-100 cutoff when a full list is available and reach at least 85% of the median of the twenty strongest known scores. This relative floor and a minimum estimated gain of max(0.5 pp, 0.25% of that benchmark) keep tiny hypothetical tail gains out of Farm. These thresholds are heuristics, not a claim that every score below them is worthless. Practice remains available for lower-value training.

FC accuracy blends local passed-run accuracy with the weighted 60th percentile of comparable near-FC achievements (25% ordinary accuracy, 75% demonstrated good-run accuracy). Matched top near-FCs receive a bounded weight increase. Direct recent complete attempts remain stronger evidence and can reject a target. The model does not assume an SS or raise accuracy to force a high pp number.

Rank uses estimated weighted profile gain, estimated FC likelihood, retry duration, uncertainty, relative pp efficiency and community farm prevalence. This favours valuable, repeatable completions over maximum theoretical pp alone. Maximum pp is a 100% FC; predicted pp is also conditional on an FC at predicted accuracy. The estimate does not include failed-attempt pp or bonus pp. Top-100 profile weighting is approximate.

Candidates qualify through community prevalence or a current 99% FC pp value at least 10% above the catalogue median for their effective mod and half-star band. This second route avoids depending entirely on historical crowd data when the calculator or mod distribution differs. Both routes still require the same personal performance fit. Community prevalence comes from osu!pps top-score use, adjusted for popularity and map age. It is a proxy for farm efficiency, not proof that a map is objectively overweighted under the current calculator. Crowdsourced data and the current pp system can disagree.

## Practice

Similarity now includes aim, speed, effective AR/OD/CS, density, duration, regular-circle burst and sustained-run demands, slider fraction, median spacing and rhythm variation. Burst success alone cannot establish sustained-stream ability. Per-mod profile summaries report weighted 15th/50th/85th percentile ranges and broad map families. These aggregate descriptors do not capture every technical pattern.

Training leads compare outcomes across maps of similar total difficulty while holding other demands broadly stable. A focus requires at least five comparisons spanning three maps. This establishes an association worth practising, not the cause of a particular miss. Where evidence is insufficient, the plan uses balanced control rather than guessing a weakness. The interface presents one map at a time: a warm-up, two focused maps played twice each, and a transfer check. Warm-up and training use the same mod setup so preparation does not switch reading conditions. Session progress is saved in the browser per account, and skipped maps remain distinct from marked-played maps. Marking a map played only tracks navigation; the final review reports new submitted score IDs and timestamps, without claiming that manual completion proves improvement.

## What speed and UR mean

Effective song BPM is read from the individual beatmap and adjusted by clock rate. Burst and sustained-run descriptors parse regular consecutive circle sequences from the actual hit objects. A burst requires at least four circles and a sustained run requires at least sixteen, with close-to-regular spacing. Equivalent stream BPM is 15,000 divided by the median real-time gap in milliseconds. These descriptors omit slider ticks, spinner actions and irregular rhythms; they are not a measured personal maximum BPM or proof that the player hit that section cleanly.

UR is ten times the standard deviation of hit errors. Aggregate accuracy, misses and judgement counts do not reveal those errors. The service deliberately returns no UR value until validated replay hit-error analysis is available. Replay analysis is not implemented in this release.

## Research

- [osu! API score endpoints and score fields](https://osu.ppy.sh/docs/)
- [Official unstable rate definition](https://osu.ppy.sh/wiki/en/Gameplay/Unstable_rate)
- [Official approach-rate and mod timing explanation](https://osu.ppy.sh/wiki/en/Beatmap/Approach_rate)
- [Official PP weighting formula](https://osu.ppy.sh/wiki/en/Performance_points/Weighting_system)
- [Player discussion of repeatable farming](https://www.reddit.com/r/osugame/comments/10lemix/how_do_people_farm/)
- [Player discussion of consistency practice](https://osu.ppy.sh/community/forums/topics/1455145)
- [Official performance points explanation](https://osu.ppy.sh/wiki/en/Performance_points)
- [Player-authored burst and stream guide](https://osu.ppy.sh/community/forums/topics/1298816), used for distinguishing control, speed and sustained demand, not its unrelated health claims.
- [Player-authored consistency guide](https://osu.ppy.sh/community/forums/topics/1542959)

Player guides offer practical hypotheses rather than controlled evidence of an optimal training algorithm. This model is an explainable starting point that should be checked against future scores, not a promise of a perfect map.

## Farm browsing and attempt cost

Efficient ranks `weighted_gain * fc_likelihood / ((map_seconds + 12) / 60)`, adjusted by bounded crowd evidence, catalogue PP efficiency and confidence. Each attempt is charged the full map duration plus restart overhead; early-failure timing is not observed. This rate is a heuristic, not a calibrated prediction of actual earnings per minute. Higher PP ranks `weighted_gain * sqrt(fc_likelihood) / sqrt(attempt_minutes)` with the same evidence adjustments, explicitly trading completion reliability for larger gains. Neither mode sorts by SS PP alone.

Higher PP may extend a demonstrated near-FC envelope by at most 0.5 stars and 20% on aim, speed or density, with only one of these axes rising over 8%. Reading, sustained-stream length and burst/stream tempo gates remain identical to Efficient. Additional demand reduces forecast accuracy and FC likelihood; direct failed attempts still reject a candidate. The service retains up to 180 distinct maps from each ranking and merges the pools. The browser filters and pages this pool in batches of 30 without requesting new calculations. Catalogue coverage can limit the number of genuinely supported targets.

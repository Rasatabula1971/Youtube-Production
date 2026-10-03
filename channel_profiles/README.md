# Channel Voice Profiles

Channel Voice is the writing/personality layer for a specific YouTube channel.
It is deliberately separate from:

- niche selection;
- Story/Script psychology;
- Short vs long-form format logic; and
- Voice Performance controls such as emotion, intensity, speed and pauses.

The same production system can therefore serve very different channels without
hard-coding one global personality.

## Current state

No channel has been chosen yet. The active selector points to:

`profiles/default_unconfigured.json`

That profile is intentionally `UNCONFIGURED`.

When the active profile is unconfigured, Story Planning and Script Writing must
not infer a persistent channel voice from the niche, title, source videos or
generic creator advice. Existing research, psychology and format rules continue
to operate normally.

## Future channel setup

Once a channel thesis and target viewer are chosen, create a new profile under
`profiles/` and validate it before changing `active_profile.json`.

An approved profile describes:

- target viewer and assumed knowledge;
- narrator role and authority style;
- tone;
- technical-language policy;
- sentence style;
- storytelling preferences;
- prohibited phrases/styles; and
- evidence/claim style.

Profiles are versioned. Do not silently overwrite the meaning of an existing
version. A later learning stage may justify Voice v2, v3 and so on after the
channel has real published evidence.

Only `APPROVED` profiles may influence generation. The default
`UNCONFIGURED` profile is a fail-safe, not a generic voice.

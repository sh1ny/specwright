# Playtest craft

Load this when writing a question, choosing a session shape, observing play, grading findings or translating a feel word into values.

## Writing the question

Keep the feel words in the question, but phrase it as a choice with a way out, so the user is not handed the expected answer.

| Weak | Better |
|---|---|
| "Does the landing feel weighty?" | "Is the landing weighty, floaty, or something else?" |
| "Don't you think the boss is too hard?" | "How many attempts did the boss take, and where did you lose most?" |
| "The map is clear, right?" | "Where did you think you had to go next?" |

In open debriefs ask what the player noticed, not whether a named quality was present. Do not explain a mechanic beforehand when discoverability is part of the question.

Behaviour outweighs words. When the user is also the designer, ask for moments rather than opinions: "Where did you retry? What did you press first?"

## What to observe

These are the signals hypotheses are built from:

- deaths, and where they happen;
- retries per obstacle;
- time to first success at the thing under test;
- the first input pressed on arrival;
- pauses, hesitation and backtracking;
- what was skipped or never seen.

## A hint is a finding

Any hint, nudge or answer the observer had to give is recorded as a finding: what was asked, and at what point. It marks a spot the game did not teach.

## Fact, opinion, suggestion

Keep three things apart in every finding:

- fact: "fell into the pit four times at the second gap";
- opinion: "the gap is too wide";
- suggestion: "widen the landing ledge".

Tuning follows the fact. The opinion is a hypothesis to test, not a result.

## Severity

One scale, used for every finding, written as a word and never shown by colour alone:

| Word | Meaning |
|---|---|
| blocker | the question cannot be answered, or a pillar fails |
| major | the feel words are missed |
| minor | noticed, does not change the answer |
| note | polish or an idea |

## Four ways a player fails

| Kind | Meaning | Owner |
|---|---|---|
| lost | does not know where to go | wayfinding and signposting: `gamedev-ux`; level layout: `gamedev-design` |
| stuck | knows where, cannot get past | difficulty or puzzle clarity: `gamedev-design`; a bug task when no way forward exists |
| bored | can go on, does not want to | pacing and reward: `gamedev-design`; dragging story beats: `gamedev-narrative` |
| missed content | passed something meant to be seen | signposting: `gamedev-ux`; placement: `gamedev-design` |

## Feel-word map

A feel word points at a small set of values to look at first. Use the table to propose candidates, never to decide the fix alone. It holds no numbers on purpose: values come from the project's data and its playtests.

| Feel word | Values to look at |
|---|---|
| floaty | apex time (time to the top of a jump), rise and fall gravity, air control, fall speed cap |
| sluggish, unresponsive | input delay, startup frames, input buffer window, acceleration |
| slippery | deceleration, friction, turn speed |
| stiff | acceleration curves, animation blending, coyote time |
| unfair | telegraph length, attack versus hurt area sizes, recovery and invulnerability windows |
| weightless (hits) | hit pause, knockback, impact sound and screen effect (respect the reduced-motion setting) |
| laggy (online) | see network feel in `playtest-kinds.md` |

Change one or two values at a time and retest, so the entry can say which move helped.

## Session shapes

- **Solo feel check** by the user: the default, short.
- **Guided**: the observer sets a task ("reach the gate") and may answer questions. Good for focused tuning.
- **Unguided**: the player gets the build and no instructions beyond starting it; the observer stays silent and notes behaviour. The only honest test of learnability.
- **First minutes**: after the opening few minutes ask whether the player understood the goal and the controls, which features they found or missed, and any moment they enjoyed.
- **Paper or rules session**: before code exists, or for a system's rules. Explain the rules once, then stay silent; confusion is data. Use new testers each round, because a tester who learned the rules cannot unlearn them.
- **Fresh eyes**: someone new to the game plays; the user runs the session and the agent supplies the question script.
- **Focused**: one mechanic or one value.
- **Regression replay**: after a tuning change, replay what earlier playtests accepted.

## Tester bias

The designer knows the answers. Team mates and friends tend to be kind, or skilled. Genre fans differ from newcomers. Record who played (designer, team, friend, fresh player) and weigh the verdict by it. Describe testers neutrally.

## Handicap test (optional)

With no fresh player available, the designer can play under a handicap: the non-dominant hand, an unfamiliar device, a control scheme they do not normally use. It approximates a newcomer on motor difficulty only. It does not test understanding, and it does not lift the low-confidence mark.

## Small samples

One player is one data point. State how many sessions back a verdict. Prefer "tune and retest" to large swings.

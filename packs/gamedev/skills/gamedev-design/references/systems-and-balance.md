# Systems and balance

Use this when an economy, a curve, a resource, randomness or difficulty is in play, or when a balance problem needs a diagnosis. The GDD states intent, ranges and hypotheses. The live values live in data the game loads. Every figure here is a starting hypothesis to tune, never a rule.

A finding is always three things: the fault, the evidence seen, and the smallest fix.

## Economy

**Sources and sinks.** Every resource, currency or reward has named sources (where it enters) and named sinks (where it leaves) in the GDD. A source without a sink is a finding: the stock grows until the resource means nothing. A sink without a source is a finding too: the player runs dry.

**Converters and traders.** A converter turns one resource into another by a rule (wood into planks). A trader exchanges with a party (a merchant with prices and a stock). They behave differently: a converter has a fixed ratio the player can plan around, a trader has a party who can run out, change price or refuse. Say which each exchange is.

**Earn time per meaningful purchase.** How long does the player play to afford something worth having? Write the target as a range (for example 3 to 6 minutes of normal play, a hypothesis), and check that it grows as items matter more.

**Cost-curve shape.** Decide if costs rise linearly, geometrically or in steps, and what each shape does. Linear feels steady and soon becomes cheap. Geometric slows the player and can stall them. Steps give clear goals and cliffs. Pick one on purpose and state why.

**Power budget per tier.** Give each tier of items or upgrades a budget of total benefit, then price every item against it. An item well above its tier's budget is overpowered; one well below is a trap.

**Worked example (invented).** A forager sells berries at 2 coins each and may spend 20 coins on a basket that holds 12 berries. Check: a full basket is worth 12 x 2 = 24 coins, so the basket pays for itself in one full trip, with 4 coins to spare (24 - 20). If the target is that a basket repays after about three trips (a hypothesis), the basket is under-costed or the berry price is too high. The fix is to price the basket near 3 x 24 = 72 coins, or to lower the berry price. Then check what else sells for berries, because a shared value changes them too.

## Feedback loops

- **Reinforcing:** a lead snowballs. A player who wins resources gets stronger and wins more.
- **Balancing:** a lead is pulled back. A player ahead meets harder rivals, higher costs or less luck.

For each loop in the design, ask which kind it is, and whether it is wanted. A reinforcing loop with no balancing partner ends the game early. A balancing loop with no reinforcing partner makes effort feel pointless. Find the comeback path: how does a player who is behind get back into the game? Is any catch-up visible to the player? Hidden rubber-banding costs trust when it is found: if used, say what it costs, tell the user, and consider telling the player.

## Balance method

1. **Diagnose the side.** Is the problem an overpowered benefit (fix the benefit) or an under-costed option (fix the cost)? The two fixes are different; a wrong guess moves the problem.
2. **Price in one currency.** Convert every option to one currency of value (time, damage, safety) so options can be compared. An option that cannot be priced cannot be balanced.
3. **Local feel early, global balance late.** Tune how one action feels first. Tune the whole economy and the content spread only once most content exists. Early global tuning is redone.
4. **Name the blast radius.** Before a shared value changes, list what it could break. A change to a base damage number touches every weapon that uses it.
5. **Change one thing at a time**, and record the intent with the change.

## Boundary probing

Test the minimum and maximum of every range, including zero, negative and the single hit that ends it all.

- What happens at zero? At the cap? One below and one above?
- What if the player holds the cap resource forever?
- Which values are knobs the designer will tune, and which are deliberate constants? Mark the constants.
- Does any knob make others irrelevant (a damage multiplier that makes armour moot)?
- Can a one-shot, or an infinite loop of cheap actions, break the design?

## Randomness placement

- **Input randomness** happens before the player's decision: a random map, a random hand. The player plans around it.
- **Output randomness** happens after the decision: a miss, a failed roll. The player suffers it.

Input randomness makes decisions richer. Output randomness that carries weight needs streak protection, so a run of bad luck cannot end a session on its own. The rule of thumb: randomise the situation, never the result of skill.

## Difficulty and flow

**Flow channel.** Csikszentmihalyi's model: challenge that rises with skill keeps the player engaged; too far above is anxiety, too far below is boredom. Shape the curve as a sawtooth of rising tension and release, not a straight climb.

**Fair challenge.** The player blames themselves, sees a path, and retries cheaply. If any of the three fails, treat it as a finding.

**Knobs live in data.** Difficulty settings are data the game loads. The GDD names the axes and the intent.

**Assist styles.**
- chosen: the player picks (a switch, a setting);
- adaptive: the game changes things from the player's results. Say whether the player is told;
- granular: several small switches rather than one level.

**Cost of a retry.** State it: time to return to the attempt, what is lost, what is kept. A cheap retry allows harder challenges.

## Difficulty axes

| Axis | What it taxes | Lowered by |
|---|---|---|
| execution | timing and precision | slower speed, wider windows, aim help |
| knowledge | what the player must know or remember | hints, a journal, signposting |
| resource | stock the player must manage | more supplies, lower costs |
| time | pressure from a clock or pace | pause, longer timers |
| decision load | how many things to weigh at once | fewer simultaneous threats, clearer UI |

Ask which axes the game uses, which the player can lower, and what the stance on frustration is: which failures should sting and which must never feel unfair.

## Design-fault catalogue

Each fault lists the signs and the smallest fix. Cite evidence from the GDD or a playtest, never taste alone.

| Fault | Signs | Smallest fix |
|---|---|---|
| dominant strategy | Players converge on one option; others are never chosen | Add a cost to the favourite, or a counter, or a benefit to the others |
| choices with nothing given up | The player can have everything; choices do not exclude | Add a limit (slots, time, weight) so a choice gives something up |
| complexity outrunning depth | Many rules, few real decisions; rules are learned but change nothing | Cut a rule, or make two rules interact |
| missing or misleading telegraph | The player dies without seeing why, or a cue means two things | Give each threat one clear, early cue |
| a skill check that becomes mandatory | Something meant as optional gates progress | Provide an alternative route or an assist |
| scope outrunning the ability to tune | More content than can be balanced | Cut content, or tune a smaller set deeply first |
| source without sink | A resource only grows | Add a sink the player wants, or cap the source |
| competing progression loops | The player is pulled two ways at once | Merge or demote one to a side system |
| diverging scaling curves | Player power and enemy power drift apart | Tie both to the same driver, or add a corrector |
| undefined combined states | Two systems fire together with no stated result | Define the combined result or an order of precedence |

## Holism review

Read the whole design for these cross-system faults:

- Are there competing progression loops, or one player identity?
- Is the attention budget at the busiest moment stated and plausible? How many things does the player track at once?
- Is there a dominant strategy anywhere across systems?
- Does each currency have sources and sinks?
- Do scaling curves diverge unchecked?
- Does one change to a shared value break other systems?

### Cross-system moment walk

Pick three to five moments where several systems fire at once (a fight at low health during a timed event with a shop open). For each, check:

- order: which system resolves first, and is it stated?
- double rewards: does one event pay twice?
- contradictory feedback: do two cues say opposite things?
- undefined combined states: what happens when two rules disagree?

Write the results as findings with the section they point at.

## Reward ethics

A reward condition the player would not enjoy meeting is a finding. Watch for appointments, paid randomness, social pressure, and streaks that punish a missed day. Variable-ratio rewards are never simply good: name their compulsion risk and ask what the design wants from them. Do not tune monetisation. Live-service and analytics engineering are out of scope for this skill.

## Motivation notes

Lead with self-determination theory (Deci and Ryan): autonomy (meaningful choice), competence (growing mastery with visible feedback), relatedness (connection to others or to characters). A motivation profile can be described as a blend of these. Bartle's player types are vocabulary for a conversation; they are not a measurement and not a split of a real audience. Rewards the player expects can crowd out the enjoyment of an act; signals of mastery tend not to.

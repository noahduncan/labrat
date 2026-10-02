# Labrat

Purpose: To practice python as a web language and think through the experimentation domain.

## Planning

Experimentation has decent amount of depth, but here we are going to focus on the primary facets of it:
1. [x] List of experiments / feature flags
2. [x] Assignment algorithm
3. [ ] Basic code interface (check if flag is on)
4. [ ] Exposure log
5. [ ] Action log
6. [ ] Reporting / significance testing

### Experiment / feature flag definitions
* Feature Flags
  * id
  * name
  * enabled
* Experiments
  * id
  * feature_flag_id
  * name
  * prediction_description
  * split
  * start_at
  * end_at

### Assignment algorithm
Bucket = (int) hash(name + user_id) % 100;

### Code interface
`if labrat.flagOn(flag_name) ...`

### Exposure log
In this case, we can log an exposure in the block immediately after the feature flag check:
`if labrat.flagOn(flag_name) labrat.recordExposure(flag_name, user)`

This is rudimentary, if the feature flag or experiment contains parameters or other variants, we'd need to record the active variant as well.

Exposure Table:
* id
* created_at
* feature_flag_id
* user_id

### Action log
Triggered somewhere else, maybe front-end or back-end code handlers for a button click.
`labrat.recordAction(flag_name, user, action)`

Action Table:
* id
* created_at
* feature_flag_id
* user_id
* action

### Reporting
Visualize action rates across variants during the experiment.

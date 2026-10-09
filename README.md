# Labrat

Purpose: To practice python as a web language and think through the experimentation domain.

## Planning

Experimentation has decent amount of depth, but here we are going to focus on the primary facets of it:

1. [x] List of experiments / feature flags
2. [x] Assignment algorithm - changing to key on experiment slug
3. [ ] Basic code interface
    * [ ] check if flag is on
    * [x] fetch flag/experiment config
4. [ ] Exposure log
    * [ ] back-end
    * [ ] client
5. [ ] Action log
    * [ ] back-end
    * [ ] client
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
    * split_a
    * split_b
    * start_at
    * end_at

### Assignment algorithm

Bucket = (int) hashlib.sha256 (experiment.slug + ":" + user_id) % 100;

### Code interface

* Fetch config
    * For this version, will use polling, but at scale pub/sub and/or config caching is needed.
* Check which flags are enabled: `if labrat.is_flag_on(flag_name) ...`
    * If no experiment active: = feature flag enabled state
    * If experiment active: = use assignment algorithm with experiment config for result

### Exposure log

In this case, we can log an exposure in the block immediately after the feature flag check:
`if labrat.is_flag_on(flag_name) labrat.record_exposure(experiment, user)`

This is rudimentary, if the feature flag or experiment contains parameters or other variants, we'd need to record the
active variant as well. It would be possible that the active variant and parameters could be derived later, this would
add burden to the reporting platform where normalized data storage is harder to query. Having de-normalized data storage
provides an easier and faster query surface for data aggregation.

Exposure Table:

* id
* created_at
* experiment_id
* user_id

**Questions:**

* Who should own the exposure data? It feels a little funny to have a client say "I exposed user X to experiment Y" from
  a "client has too much power" / bad-actors perspective. That concern feels like it could be reasonably mitigated by
  server-side validations (can't expose to an experiment that isn't running...but what if you have a cache of exposure
  events that come in bulk after an experiment ends...oy!...I guess some kind of buffering window allowing exposures to
  be logged for some amount of time after experiment end).

### Action log

Triggered somewhere else, maybe front-end or back-end code handlers for a button click.
`labrat.record_action(user, action)`

Action Table:

* id
* created_at
* user_id
* action

### Reporting

* Conversion rate
* Significance test

# Considerations

* I've envisioned this framework as a centralized experiment store with individual apps reaching out to it via API to
  log exposures and actions. However, this has downsides in that all experimentation features must be implemented
  centrally which adds the complexity of a multi-tenant application. Another approach would be to build the
  experimentation platform as a Django plugin so that it can be reused in different applications and extended there as
  needed. This solves some problems, but gains other considerations like an extensibility surface, and complexities
  around version updates to an extended system.
* Academically, having tables for exposures and actions is convenient. However, there is a good chance that reality
  would dictate other needs. Likely applications are using their own tracking platforms like hotjar, or google analytics
  that allow them to track custom fields / metrics across page loads. It may be desired to hook exposures and metrics
  into external data apis or data warehouses in order to reduce the integration burden and redundancy on other product
  teams.

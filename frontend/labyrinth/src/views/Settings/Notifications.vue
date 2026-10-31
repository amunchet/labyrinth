<template>
  <div class="text-left">
    <h3>Notification backoff</h3>
    <p class="text-muted">
      A problem that keeps failing is announced less and less often, so new
      problems still stand out. Applies to Alertmanager alerts (service checks
      and alive checks on monitored hosts) and to the Proxmox disk space and EC2
      unmatched instance emails.
    </p>
    <b-form v-if="settings" @submit.prevent="save">
      <b-form-checkbox v-model="settings.enabled" switch class="mb-3">
        Back off repeat notifications
      </b-form-checkbox>
      <b-form-group
        label="First reminder after (minutes)"
        label-for="backoff-first"
        description="How long after a problem's first notification the first reminder comes."
      >
        <b-form-input
          id="backoff-first"
          v-model="settings.first_minutes"
          type="number"
          number
          min="1"
          :disabled="!settings.enabled"
        />
      </b-form-group>
      <b-form-group
        label="Multiplier"
        label-for="backoff-multiplier"
        description="Each gap between reminders is this many times longer than the one before. 1 keeps a fixed interval."
      >
        <b-form-input
          id="backoff-multiplier"
          v-model="settings.multiplier"
          type="number"
          number
          min="1"
          max="100"
          step="0.5"
          :disabled="!settings.enabled"
        />
      </b-form-group>
      <b-form-group
        label="Longest gap (hours)"
        label-for="backoff-max"
        description="Reminders never get further apart than this."
      >
        <b-form-input
          id="backoff-max"
          v-model="settings.max_hours"
          type="number"
          number
          min="1"
          max="8760"
          :disabled="!settings.enabled"
        />
      </b-form-group>

      <b-alert v-if="error" show variant="danger">{{ error }}</b-alert>
      <p v-else-if="settings.enabled">
        Reminders come <b>{{ schedule }}</b> after a problem's first
        notification.
      </p>
      <p v-else>
        Alertmanager alerts repeat at its own <code>repeat_interval</code>, and
        the disk space and EC2 emails go out every hour.
      </p>

      <b-button type="submit" variant="primary" :disabled="saving || !!error">
        <b-spinner small v-if="saving" class="mr-2" />
        Save
      </b-button>
    </b-form>
    <b-spinner v-else />

    <p class="text-muted small mt-3">
      New problems always notify right away, and a problem that clears and later
      comes back counts as new. Between reminders an Alertmanager alert stays
      active but is muted by a silence created by Labyrinth, which you can see,
      and expire early, in Alertmanager. Alertmanager's own
      <code>repeat_interval</code> is still the shortest gap between repeats.
    </p>
  </div>
</template>
<script>
import Helper from "@/helper";

// "45m", "1.5h", "24h"
function duration(minutes) {
  if (minutes < 60) {
    return Math.round(minutes) + "m";
  }
  return Math.round((minutes / 60) * 10) / 10 + "h";
}

export default {
  name: "Notifications",
  data() {
    return {
      settings: null,
      saving: false,
    };
  },
  computed: {
    error: function () {
      const s = this.settings;
      if (!(s.first_minutes > 0)) {
        return "The first reminder must come after more than 0 minutes.";
      }
      if (!(s.multiplier >= 1 && s.multiplier <= 100)) {
        return "The multiplier must be between 1 and 100.";
      }
      if (!(s.max_hours > 0 && s.max_hours <= 8760)) {
        return "The longest gap must be more than 0 and at most 8760 hours (a year).";
      }
      if (!(s.max_hours * 60 >= s.first_minutes)) {
        return "The longest gap can't be shorter than the first reminder.";
      }
      return "";
    },
    schedule: function () {
      // Times of the first few reminders, until the gap stops growing
      const s = this.settings;
      const max = s.max_hours * 60;
      let gap = s.first_minutes;
      let at = 0;
      const times = [];
      for (let i = 0; i < 6; i++) {
        at += gap;
        times.push(duration(at));
        const next = Math.min(gap * s.multiplier, max);
        if (next === gap) {
          return times.join(", ") + ", then every " + duration(gap);
        }
        gap = next;
      }
      return times.join(", ") + ", ...";
    },
  },
  methods: {
    load: /* istanbul ignore next */ function () {
      Helper.apiCall("alert-backoff", "settings", this.$auth)
        .then((res) => {
          this.settings = typeof res === "string" ? JSON.parse(res) : res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    save: /* istanbul ignore next */ function () {
      this.saving = true;
      Helper.apiPost(
        "alert-backoff",
        "",
        "settings",
        this.$auth,
        JSON.stringify(this.settings)
      )
        .then((res) => {
          this.settings = JSON.parse(res);
          this.$store.commit("updateError", "Notification backoff saved");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        })
        .finally(() => {
          this.saving = false;
        });
    },
  },
  mounted: function () {
    this.load();
  },
};
</script>

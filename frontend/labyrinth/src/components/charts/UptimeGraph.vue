<template>
  <div class="uptime-graph">
    <div class="uptime-graph-header">
      <div class="uptime-status">
        <span :class="['status-dot', statusBgClass(overallStatus)]"></span>
        <span class="status-text">{{ statusLabel(overallStatus) }}</span>
      </div>
      <div class="uptime-percent" v-if="uptimePercent !== null">
        {{ uptimePercent }}% uptime
      </div>
    </div>

    <div class="uptime-bars" v-if="buckets.length">
      <div
        v-for="(bucket, idx) in buckets"
        :key="idx"
        v-b-tooltip.top="bucket.tooltip"
        tabindex="0"
        :aria-label="bucket.tooltip"
        :class="['uptime-bar', statusBgClass(bucket.status)]"
      ></div>
    </div>
    <div class="uptime-empty text-muted" v-else>
      No metric history available yet.
    </div>

    <div class="uptime-range-labels text-muted" v-if="buckets.length">
      <span>{{ buckets[0].label }}</span>
      <span>{{ buckets[buckets.length - 1].label || "now" }}</span>
    </div>

    <div class="uptime-legend">
      <span class="legend-item">
        <span class="status-dot green-bg"></span> Operational
      </span>
      <span class="legend-item">
        <span class="status-dot red-bg"></span> Down
      </span>
      <span class="legend-item">
        <span class="status-dot orange-bg"></span> Unknown
      </span>
      <span class="legend-item">
        <span class="status-dot bar-none"></span> No data
      </span>
    </div>
  </div>
</template>

<script>
import Helper from "@/helper";

const BUCKET_COUNTS = { day: 30, hour: 24, check: 50 };
const BUCKET_SIZE_MS = { day: 86400000, hour: 3600000 };
const STATUS_LABELS = {
  up: "Operational",
  down: "Down",
  unknown: "Unknown",
  none: "No Data",
};

export default {
  name: "UptimeGraph",
  props: {
    records: {
      type: Array,
      default: () => [],
    },
    granularity: {
      type: String,
      default: "day",
      validator: (v) => ["day", "hour", "check"].indexOf(v) !== -1,
    },
  },
  computed: {
    bucketCount() {
      return BUCKET_COUNTS[this.granularity] || BUCKET_COUNTS.day;
    },
    bucketSizeMs() {
      return BUCKET_SIZE_MS[this.granularity];
    },
    sortedRecords() {
      return this.records
        .filter((r) => r && typeof r.timestamp === "number")
        .slice()
        .sort((a, b) => a.timestamp - b.timestamp);
    },
    buckets() {
      if (this.granularity === "check") {
        return this.buildCheckBuckets();
      }
      return this.buildTimeBuckets();
    },
    bucketsWithData() {
      return this.buckets.filter((b) => b.status !== "none");
    },
    uptimePercent() {
      if (!this.bucketsWithData.length) return null;
      const up = this.bucketsWithData.filter((b) => b.status === "up").length;
      return ((up / this.bucketsWithData.length) * 100).toFixed(2);
    },
    overallStatus() {
      for (let i = this.buckets.length - 1; i >= 0; i--) {
        if (this.buckets[i].status !== "none") return this.buckets[i].status;
      }
      return "none";
    },
  },
  methods: {
    formatDate: Helper.formatDate,
    statusLabel(status) {
      return STATUS_LABELS[status] || STATUS_LABELS.none;
    },
    statusBgClass(status) {
      return (
        { up: "green-bg", down: "red-bg", unknown: "orange-bg" }[status] ||
        "bar-none"
      );
    },
    formatBucketLabel(ms) {
      if (this.granularity === "day") {
        return this.formatDate(ms);
      }
      return this.formatDate(ms) + " " + this.formatDate(ms, true);
    },
    summarize(group) {
      if (!group.length) {
        return { status: "none", count: 0, failed: 0, unknown: 0 };
      }
      const failed = group.filter((r) => r.judgement === false).length;
      const unknown = group.filter((r) => r.judgement === -1).length;
      let status = "up";
      if (failed > 0) {
        status = "down";
      } else if (unknown > 0) {
        status = "unknown";
      }
      return { status, count: group.length, failed, unknown };
    },
    tooltipFor(status, label, summary) {
      const text = this.statusLabel(status);
      if (status === "down") {
        return `${text} (${summary.failed}/${summary.count} checks failed) · ${label}`;
      }
      if (status === "unknown") {
        return `${text} (${summary.unknown}/${summary.count} checks stale) · ${label}`;
      }
      if (status === "none") {
        return `${text} · ${label || "no checks recorded"}`;
      }
      return `${text} · ${label}`;
    },
    buildCheckBuckets() {
      const count = this.bucketCount;
      const recent = this.sortedRecords.slice(-count);
      const bars = recent.map((r) => {
        const label = this.formatBucketLabel(r.timestamp * 1000);
        const summary = this.summarize([r]);
        return {
          status: summary.status,
          label,
          tooltip: this.tooltipFor(summary.status, label, summary),
        };
      });
      const missing = count - bars.length;
      if (missing <= 0) {
        return bars;
      }
      const placeholders = new Array(missing).fill(null).map(() => ({
        status: "none",
        label: "",
        tooltip: this.tooltipFor("none", "", {
          count: 0,
          failed: 0,
          unknown: 0,
        }),
      }));
      return placeholders.concat(bars);
    },
    buildTimeBuckets() {
      const size = this.bucketSizeMs;
      const count = this.bucketCount;
      const nowBucketEnd = Math.ceil(Date.now() / size) * size;
      const bars = [];
      for (let i = count - 1; i >= 0; i--) {
        const end = nowBucketEnd - i * size;
        const start = end - size;
        const inRange = this.sortedRecords.filter((r) => {
          const t = r.timestamp * 1000;
          return t >= start && t < end;
        });
        const summary = this.summarize(inRange);
        const label = this.formatBucketLabel(start);
        bars.push({
          status: summary.status,
          label,
          tooltip: this.tooltipFor(summary.status, label, summary),
        });
      }
      return bars;
    },
  },
};
</script>

<style scoped>
.uptime-graph {
  padding: 0.75rem 0;
}
.uptime-graph-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.6rem;
}
.uptime-status {
  font-weight: 600;
  font-size: 1.05rem;
}
.uptime-percent {
  color: #64646e;
  font-size: 0.9rem;
}
.status-dot {
  display: inline-block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-right: 0.4rem;
}
.uptime-bars {
  display: flex;
  align-items: stretch;
  gap: 2px;
  width: 100%;
  height: 36px;
}
.uptime-bar {
  flex: 1 1 0;
  min-width: 3px;
  border-radius: 3px;
  cursor: pointer;
  transition: filter 0.1s ease-in-out, transform 0.1s ease-in-out;
}
.uptime-bar:hover,
.uptime-bar:focus {
  filter: brightness(1.12);
  transform: scaleY(1.08);
  outline: none;
}
.bar-none {
  background-color: #bfbfbd;
}
.uptime-empty {
  padding: 0.75rem 0;
}
.uptime-range-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.78rem;
  margin-top: 0.3rem;
}
.uptime-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 0.6rem;
  font-size: 0.8rem;
  color: #64646e;
}
.legend-item {
  display: inline-flex;
  align-items: center;
}
</style>

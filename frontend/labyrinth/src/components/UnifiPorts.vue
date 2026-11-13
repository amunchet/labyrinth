<template>
  <div class="unifi-ports">
    <div class="port-grid">
      <div
        v-for="port in ports"
        :key="port.idx"
        :class="'port ' + portState(port)"
        :title="portTitle(port)"
      >
        {{ port.idx }}
        <font-awesome-icon v-if="port.poe" icon="bolt" class="poe" />
      </div>
    </div>
    <table class="table table-sm mb-0 mt-1 port-list">
      <tr v-for="port in in_use" :key="port.idx">
        <td class="idx">{{ port.idx }}</td>
        <td>
          <div
            v-for="item in port.connected"
            :key="item.mac"
            :class="{ 'text-muted': !item.active }"
          >
            <font-awesome-icon
              v-if="item.upstream"
              icon="arrow-up"
              title="Uplink"
              class="mr-1"
            />
            <b-link v-if="item.key" @click="$emit('select', item.key)">{{
              itemName(item)
            }}</b-link>
            <span v-else>{{ itemName(item) }}</span>
            <small v-if="!item.active"> (not connected now)</small>
          </div>
        </td>
        <td class="speed">{{ portSpeed(port) }}</td>
      </tr>
    </table>
  </div>
</template>
<script>
// A UniFi switch's ports (from /inventory/ or /unifi/): a port grid coloured by
// link state, and what is plugged into each port in use
export default {
  name: "UnifiPorts",
  props: {
    ports: { type: Array, required: true },
  },
  computed: {
    in_use() {
      return this.ports.filter((x) => x.connected && x.connected.length);
    },
  },
  methods: {
    portState(port) {
      if (!port.enabled) {
        return "disabled";
      }
      return port.up ? "up" : "down";
    },
    portSpeed(port) {
      if (!port.speed) {
        return "";
      }
      return port.speed >= 1000 ? port.speed / 1000 + "G" : port.speed + "M";
    },
    itemName(item) {
      return item.name || item.ip || item.mac;
    },
    portTitle(port) {
      let lines = [
        port.name +
          " – " +
          (port.enabled ? (port.up ? "up" : "down") : "disabled") +
          (port.speed ? " " + this.portSpeed(port) : "") +
          (port.media ? " " + port.media : ""),
      ];
      if (port.poe) {
        lines.push("PoE " + port.poe + " W");
      }
      (port.connected || []).forEach((x) => lines.push(this.itemName(x)));
      return lines.join("\n");
    },
  },
};
</script>
<style scoped>
.port-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}
.port {
  min-width: 1.6rem;
  padding: 0 0.15rem;
  text-align: center;
  font-size: 0.7rem;
  border-radius: 0.15rem;
  color: white;
  position: relative;
}
.port.up {
  background-color: #28a745;
}
.port.down {
  background-color: #adb5bd;
}
.port.disabled {
  background-color: #495057;
}
.poe {
  font-size: 0.55rem;
  color: #ffc107;
}
.port-list {
  font-size: 0.8rem;
}
.port-list td {
  padding: 0.1rem 0.3rem;
}
.idx,
.speed {
  width: 1%;
  white-space: nowrap;
  color: #6c757d;
}
</style>

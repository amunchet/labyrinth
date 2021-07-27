<template>
  <b-modal id="create_edit_host" title="Create/Edit Host" size="lg">
    <b-modal id="checks" size="xl" @hide="loadServices()">
      <Checks />
    </b-modal>
    <b-container>
      <b-row>
        <b-col> IP </b-col>
        <b-col>
          <b-input v-model="host.ip" />
        </b-col>
      </b-row>

      <b-row
        ><b-col>MAC </b-col><b-col><b-input v-model="host.mac" /></b-col
      ></b-row>
      <b-row
        ><b-col>Group </b-col><b-col><b-input v-model="host.group" /></b-col
      ></b-row>
      <b-row
        ><b-col>Subnet</b-col><b-col><b-input v-model="host.subnet" /></b-col
      ></b-row>
      <b-row
        ><b-col>Icon</b-col><b-col><b-input v-model="host.icon" /></b-col
      ></b-row>
      <b-row
        ><b-col>Class</b-col><b-col><b-input v-model="host.class" /></b-col
      ></b-row>
    </b-container>
    <hr />
    Service Icons:
    <b-row >
      <b-col style="display: flex;">
        <font-awesome-icon class="mt-2 mr-3" icon="chart-area" size="1x"  /><br />
        <b-select v-model="host.cpu_check" :options="[{text: '[No Service]', value: ''},...host.services.map(x=>{
          return { text: x.name, value: x.name}
          })]" size="sm" />
      </b-col>

      <b-col style="display: flex;">
        <font-awesome-icon class="mt-2 mr-3" icon="memory" size="1x"  /><br />
        <b-select v-model="host.mem_check" :options="[{text: '[No Service]', value: ''},...host.services.map(x=>{
          return { text: x.name, value: x.name}
          })]" size="sm" />
      </b-col>

      <b-col style="display: flex;">
        <font-awesome-icon class="mt-2 mr-3" icon="database" size="1x"  /><br />
        <b-select v-model="host.hd_check" :options="[{text: '[No Service]', value: ''},...host.services.map(x=>{
          return { text: x.name, value: x.name}
          })]" size="sm" />
      </b-col>
    </b-row>

    <hr />
    <b-row>
      <b-col>
          <h5>Expected Open Ports
          <b-button
            variant="link"
            class="float-right mt-0 pt-1 shadow-none"
            @click="show_add_port = !show_add_port"
          >
            <font-awesome-icon icon="plus" size="1x" />
          </b-button>
          </h5>
        <b-table
          v-if="host.open_ports"
          :items="
            ([...host.open_ports].sort()).map((x) => {
              return { port: x };
            })
          "
          striped
          :fields="['port', '_']"
        >
          <template v-slot:cell(_)="key">
            <b-button
              @click="
                () => {
                  host.open_ports = host.open_ports.filter(
                    (x) => x != key.item.port
                  );
                  $forceUpdate();
                }
              "
              variant="link"
              class="shadow-none float-right text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </template>

          <template v-slot:top-row="" v-if="show_add_port">
            <td role="cell">
              <b-input placeholder="Port:" v-model="new_port" />
            </td>
            <td role="cell">
              <b-button
                variant="success"
                class="float-right p-1 pl-2 pr-2"
                @click="
                  () => {
                    if (new_port != '') {
                      host.open_ports.push(new_port);
                    }
                    new_port = '';
                    show_add_port = false;
                    $forceUpdate();
                  }
                "
              >
                <font-awesome-icon icon="check" size="1x" />
              </b-button>
            </td>
          </template>
        </b-table>
      </b-col>
      <b-col>
        <h5>
          <a href="#" @click="$bvModal.show('checks')">Services</a>
          <b-button
            variant="link"
            class="shadow-none float-right mt-0 pt-1"
            @click="show_add_service = !show_add_service"
          >
            <font-awesome-icon icon="plus" size="1x" />
          </b-button>
        </h5>
        <b-table
          :items="host.services"
          striped
          :fields="['name', 'state', '_']"
        >
          <template v-slot:cell(_)="key">
            <b-button
              @click="
                () => {
                  host.services = host.services.filter(
                    (x) => x.name != key.item.name
                  );
                  $forceUpdate();
                }
              "
              variant="link"
              class="shadow-none float-right text-danger"
            >
              <font-awesome-icon icon="times" size="1x" />
            </b-button>
          </template>
          <template v-slot:top-row="" v-if="show_add_service">
            <td role="cell">
              <b-select placeholder="Service:" :options="services" v-model="new_services" />
            </td>

            <td>-</td>
            <td role="cell">
              <b-button
                variant="success"
                class="float-right p-1 pl-2 pr-2"
                @click="
                  () => {
                    if (new_services && new_services != '') {
                      host.services.push({
                        name: new_services,
                        state: '',
                      });
                    }
                    new_services = '';
                    show_add_service = false;
                    $forceUpdate();
                  }
                "
              >
                <font-awesome-icon icon="check" size="1x" />
              </b-button>
            </td>

          </template>
        </b-table>
      </b-col>
    </b-row>
    <b-row class="overflow-scroll" v-if="metrics.length">
      <h4>Latest Host Metrics</h4>
      <div style="max-height: 400px; overflow-y: scroll; overflow-x: hidden">
        <b-table :items="metrics" striped />
      </div>
    </b-row>

    <template #modal-footer="{ cancel }">
      <div style="width: 100%">
        <b-button class="float-left" variant="danger" @click="deleteHost()"
          >Delete</b-button
        >
        <b-button class="float-right ml-2" variant="primary" @click="saveHost()"
          >OK</b-button
        >
        <b-button class="float-right" @click="cancel()">Cancel</b-button>
      </div>
    </template>
  </b-modal>
</template>
<script>
import Helper from "@/helper";
import Checks from '@/views/Checks'
export default {
  name: "CreateEditHost",
  components: {
    Checks
  },
  props: ["inp_host"],
  data() {
    return {
      isNew: true,
      host: "",
      metrics: [],
      safe_host: {
        ip: "",
        subnet: "",
        mac: "",
        group: "",
        icon: "",
        services: [],
        class: "",
      },
      new_port: "",
      new_service: "",
      show_add_port: false,
      show_add_service: false,

      services: [],
    };
  },
  watch: {
    inp_host: function (val) {
      if (val == "") {
        this.isNew = true;
        this.host = JSON.parse(JSON.stringify(this.safe_host));
        this.metrics = [];
      } else {
        this.isNew = false;
        this.host = val;
        this.loadMetrics();
      }
    },
  },
  methods: {
    loadServices: /* istanbul ignore next */ function(){
      var auth = this.$auth
      Helper.apiCall("services", "all", auth).then(res=>{
        this.services = res.map(x=>{
          return{
            text: x.name,
            value: x.name
          }
        })
      }).catch(e=>{
        this.$store.commit('updateError', e)
      })
    },
    loadMetrics: /* istanbul ignore next */ function () {
      var auth = this.$auth;
      Helper.apiCall("metrics", this.host.mac, auth)
        .then((res) => {
          this.metrics = res;
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
    saveHost: /* istanbul ignore next  */ function () {
      var auth = this.$auth;
      var formData = new FormData();

      var host = JSON.parse(JSON.stringify(this.host));
      host["services"] = host["services"].map((x) => x["name"]);
      formData.append("data", JSON.stringify(host));
      Helper.apiPost("host", "", "", auth, formData)
        .then((res) => {
          this.$emit("update");
          this.$store.commit("updateError", res);
          this.$bvModal.hide("create_edit_host");
        })
        .catch((e) => {
          this.$store.commit("updateError", e);
        });
    },
  },
  mounted: /* istanbul ignore next */ function(){
    try{
      this.loadServices()
    }catch(e){
      this.$store.commit('updateError', e)
    }
  }
};
</script>
<style lang="scss" scoped>
.row {
  margin: 1rem;
}
h4 {
  text-align: center;
}
.overflow-scroll {
  overflow-x: scroll;
}
</style>

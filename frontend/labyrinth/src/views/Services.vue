<template>
  <b-container>
      <h4>Services</h4>
      <b-button variant="primary">Load Services Template</b-button>
  <b-row v-for="(section, idx) in data" v-bind:key="idx">
    <h2>{{section.name}}</h2>
    <b-select :options="list_children" />
    <b-button>Add Section</b-button>

    {{details}}
    <hr />
  </b-row>
</b-container>
</template>

<script>
export default {
  name: "Services",
  data() {
    return {
      data: [
        {
          name: "global_tags",
        },
        {
          name: "inputs",

        },
        {
          name: "agent",
        },
      ],

      // List children for a specific element
      list_children: ['cpu', 'disk', 'diskio', 'kernel', 'mem'],
      
      // Details - this will look for parent of whatever
      details: {
        name: "cpu",
        comment: "",
        fields: {
          "percpu" : {
            "raw" : "percpu = true",
            "comments" : [
              "Read metrics about cpu usage"
            ]
          },
          "totalcpu" : "",
          "collect_cpu_time": "",
          "report_active": "",
        }
      },
    };
  },
};
</script>

<style scoped></style>
